"""Confirms created CJ orders and pays them from the CJ wallet balance.

A CJ order is created with ``payType=3`` (create only), so on its own it would
sit in CJ's CREATED state forever and never ship. This service walks it through
the two remaining steps, confirm and pay, recording each outcome before the
next remote call:

    CREATED --confirmOrder--> CONFIRMED --payBalance--> PAID --> cj.order.paid
                                  |
                                  +--(balance too low)--> AWAITING_FUNDS (retried)

Every step starts by reading CJ's own order status, so re-running a step after
a lost response, a crash, or a concurrent retry never pays an order twice.
Payment is withheld when CJ bills more than the order was expected to cost,
and an order that cannot be paid within ``CJ_PAYMENT_MAX_WAIT_HOURS`` is
failed, which cancels it and voids the customer's card hold.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from logging import Logger
from typing import Any
from uuid import UUID

from database_layer.cj_order_attempt_repository import CJOrderAttemptRepository
from enums.cj_order_enums import CJOrderAttemptStatus
from models.cj_order_attempt_models import CJOrderAttempt
from models.outbox_models import OutboxEvent
from service_layer.cj_api_client import (
    CJDropshippingAPIClient,
    CJDropshippingAPIError,
)
from service_layer.outbox_event_service import OutboxEventService
from shared.contracts.events import (
    CJOrderFailedEvent,
    CJOrderPaidEvent,
    OrderConfirmedEvent,
)
from shared.database_layer.outbox_repository import OutboxRepository
from shared.enums.event_enums import OrderEvents
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings
from shared.utils.money import CENT
from shared.utils.supplier_pricing import SupplierRetailPricing


# CJ order statuses, as documented for getOrderDetail.
_NOT_CONFIRMED = frozenset({"CREATED", "IN_CART"})
_UNPAID = "UNPAID"
_PAID_OR_LATER = frozenset({"PENDING", "PROCESSING", "UNSHIPPED", "SHIPPED", "DELIVERED"})
_CANCELLED = "CANCELLED"


class CJPaymentPending(Exception):
    """The order could not be advanced now; a later retry may succeed."""


@dataclass(frozen=True, slots=True)
class _Snapshot:
    status: str
    amount_usd: Decimal | None


@dataclass(slots=True)
class PaymentRunReport:
    paid: int = 0
    awaiting_funds: int = 0
    held_for_review: int = 0
    failed: int = 0
    pending: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "paid": self.paid,
            "awaiting_funds": self.awaiting_funds,
            "held_for_review": self.held_for_review,
            "failed": self.failed,
            "pending": self.pending,
            "errors": self.errors[:20],
        }


class CJOrderPaymentService:
    """Drives one CJ order from created to paid, one recorded step at a time."""

    def __init__(
        self,
        settings: Settings,
        database: DatabaseSessionManager,
        api_client: CJDropshippingAPIClient,
        logger: Logger,
    ) -> None:
        self.settings: Settings = settings
        self.database: DatabaseSessionManager = database
        self.api_client: CJDropshippingAPIClient = api_client
        self.logger: Logger = logger

    # ------------------------------------------------------------------ pricing

    @staticmethod
    def expected_max_amount_usd(
        event: OrderConfirmedEvent, settings: Settings
    ) -> Decimal | None:
        """The most CJ may bill for the CJ lines of ``event`` before review.

        The customer's CAD shelf price is at least cost x markup x FX (see
        ``SupplierRetailPricing``), so dividing it back out bounds CJ's product
        cost from above; the quoted freight is added and the sum padded by the
        tolerance. Orders placed before freight was quoted carry no ceiling.
        """
        if event.shipping_cost_usd is None:
            return None
        pricing = SupplierRetailPricing.from_settings(settings)
        goods_cad = sum(
            (Decimal(str(item.price)) * item.quantity for item in event.items),
            start=Decimal("0"),
        )
        goods_usd = goods_cad / pricing.usd_to_cad_rate / pricing.markup_multiplier
        tolerance = 1 + Decimal(str(settings.CJ_ORDER_COST_TOLERANCE))
        return ((goods_usd + Decimal(event.shipping_cost_usd)) * tolerance).quantize(
            CENT, rounding=ROUND_HALF_UP
        )

    # --------------------------------------------------------------- advancing

    async def advance(self, order_id: UUID) -> CJOrderAttemptStatus | None:
        """Take the order's CJ purchase as far as it can go right now.

        Returns the resulting attempt status, or ``None`` when there is no
        unpaid CJ order for ``order_id``.

        Raises:
            CJPaymentPending: CJ is unreachable or not ready; retry later.
        """
        attempt = await self._load(order_id)
        if attempt is None or attempt.status not in CJOrderAttemptStatus.awaiting_payment():
            return CJOrderAttemptStatus(attempt.status) if attempt else None
        if not attempt.cj_order_number:
            raise CJPaymentPending(f"Order {order_id} has no CJ order number yet")

        await self._claim(order_id)
        try:
            return await self._advance_claimed(order_id, attempt, attempt.cj_order_number)
        finally:
            await self._release(order_id)

    async def _advance_claimed(
        self, order_id: UUID, attempt: CJOrderAttempt, cj_order_number: str
    ) -> CJOrderAttemptStatus | None:
        """The confirm -> pay walk, run only by the holder of the payment lease."""
        snapshot = await self._snapshot(cj_order_number)

        if snapshot.status == _CANCELLED:
            return await self._fail(order_id, f"CJ cancelled order {cj_order_number} before it was paid")
        if snapshot.status in _PAID_OR_LATER:
            return await self._record_paid(order_id, snapshot.amount_usd)
        if snapshot.status in _NOT_CONFIRMED:
            await self._confirm(cj_order_number)
            await self._set_status(order_id, CJOrderAttemptStatus.CONFIRMED)
            snapshot = await self._snapshot(cj_order_number)
            if snapshot.status in _PAID_OR_LATER:
                return await self._record_paid(order_id, snapshot.amount_usd)
        if snapshot.status != _UNPAID:
            raise CJPaymentPending(
                f"CJ order {cj_order_number} is {snapshot.status or 'unknown'}, not payable yet"
            )
        await self._set_status(order_id, CJOrderAttemptStatus.CONFIRMED, amount_usd=snapshot.amount_usd)
        return await self._pay(attempt, snapshot)

    async def advance_due(self, now: datetime | None = None) -> PaymentRunReport:
        """Retry every unpaid order not touched for a retry interval.

        Orders still unpaid after the maximum wait are failed instead.
        """
        now = now or datetime.now(timezone.utc)
        report = PaymentRunReport()
        due_before = now - timedelta(minutes=self.settings.CJ_PAYMENT_RETRY_INTERVAL_MINUTES)
        give_up_before = now - timedelta(hours=self.settings.CJ_PAYMENT_MAX_WAIT_HOURS)

        async with self.database.transaction() as session:
            due = await CJOrderAttemptRepository(session).get_due_for_payment(
                updated_before=due_before,
                limit=self.settings.CJ_PAYMENT_BATCH_SIZE,
            )
            candidates = [(attempt.order_id, attempt.date_created, attempt.last_error) for attempt in due]

        for order_id, created_at, last_error in candidates:
            try:
                if created_at <= give_up_before:
                    await self._fail(
                        order_id,
                        f"CJ order could not be paid within {self.settings.CJ_PAYMENT_MAX_WAIT_HOURS} hours"
                        + (f": {last_error}" if last_error else ""),
                    )
                    report.failed += 1
                    continue
                status = await self.advance(order_id)
            except CJPaymentPending as exc:
                report.pending += 1
                await self._note_error(order_id, str(exc))
                continue
            except Exception as exc:  # one bad order must not stall the batch
                report.errors.append(f"{order_id}: {exc}")
                self.logger.exception("CJ payment retry failed for order %s", order_id)
                continue
            match status:
                case CJOrderAttemptStatus.PAID:
                    report.paid += 1
                case CJOrderAttemptStatus.AWAITING_FUNDS:
                    report.awaiting_funds += 1
                case CJOrderAttemptStatus.RECONCILIATION_REQUIRED:
                    report.held_for_review += 1
                case CJOrderAttemptStatus.FAILED:
                    report.failed += 1
        return report

    # ------------------------------------------------------------------- steps

    async def _pay(self, attempt: CJOrderAttempt, snapshot: _Snapshot) -> CJOrderAttemptStatus:
        order_id, cj_order_number = attempt.order_id, attempt.cj_order_number
        amount = snapshot.amount_usd
        if amount is None:
            raise CJPaymentPending(f"CJ order {cj_order_number} reported no orderAmount")

        ceiling = attempt.expected_max_amount_usd
        if ceiling is not None and amount > ceiling:
            reason = (
                f"CJ billed {amount} USD for order {cj_order_number}, above the "
                f"expected maximum of {ceiling} USD; payment withheld"
            )
            self.logger.critical("RECONCILIATION REQUIRED for order %s: %s", order_id, reason)
            await self._set_status(
                order_id, CJOrderAttemptStatus.RECONCILIATION_REQUIRED, last_error=reason
            )
            return CJOrderAttemptStatus.RECONCILIATION_REQUIRED

        balance = await self._balance()
        if balance < amount:
            reason = f"CJ balance {balance} USD cannot cover {amount} USD for order {cj_order_number}"
            self.logger.critical("CJ BALANCE TOO LOW: %s. Top up the CJ wallet.", reason)
            await self._set_status(order_id, CJOrderAttemptStatus.AWAITING_FUNDS, last_error=reason)
            return CJOrderAttemptStatus.AWAITING_FUNDS

        try:
            await self.api_client.pay_balance(cj_order_number)
        except CJDropshippingAPIError as exc:
            # The payment may have gone through before the error: ask CJ.
            after = await self._snapshot(cj_order_number)
            if after.status not in _PAID_OR_LATER:
                raise CJPaymentPending(f"CJ balance payment failed: {exc}") from exc
        return await self._record_paid(order_id, amount)

    async def _confirm(self, cj_order_number: str) -> None:
        try:
            await self.api_client.confirm_order(cj_order_number)
        except CJDropshippingAPIError as exc:
            # A confirm whose response was lost has still moved the order on.
            if (await self._snapshot(cj_order_number)).status in _NOT_CONFIRMED:
                raise CJPaymentPending(f"CJ order confirmation failed: {exc}") from exc

    async def _snapshot(self, cj_order_number: str) -> _Snapshot:
        try:
            response = await self.api_client.get_order_detail(cj_order_number)
        except CJDropshippingAPIError as exc:
            raise CJPaymentPending(f"Unable to read CJ order {cj_order_number}: {exc}") from exc
        data = response.get("data") or {}
        return _Snapshot(
            status=str(data.get("orderStatus") or "").strip().upper(),
            amount_usd=_to_decimal(data.get("orderAmount")),
        )

    async def _balance(self) -> Decimal:
        try:
            response = await self.api_client.get_balance()
        except CJDropshippingAPIError as exc:
            raise CJPaymentPending(f"Unable to read the CJ balance: {exc}") from exc
        balance = _to_decimal((response.get("data") or {}).get("amount"))
        if balance is None:
            raise CJPaymentPending("CJ balance response carried no amount")
        return balance

    # ------------------------------------------------------------ persistence

    async def _load(self, order_id: UUID) -> CJOrderAttempt | None:
        async with self.database.transaction() as session:
            return await CJOrderAttemptRepository(session).get_by_field("order_id", order_id)

    async def _claim(self, order_id: UUID) -> None:
        """
        Take the payment lease, or raise CJPaymentPending if another runner
        holds it. Checked under the row lock, so exactly one caller wins.
        """
        now = datetime.now(timezone.utc)
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(order_id)
            if attempt is None:
                return
            if attempt.payment_leased_until is not None and attempt.payment_leased_until > now:
                raise CJPaymentPending(f"CJ payment for order {order_id} is already in progress")
            attempt.payment_attempts = (attempt.payment_attempts or 0) + 1
            attempt.payment_leased_until = now + timedelta(
                minutes=self.settings.CJ_PAYMENT_LEASE_MINUTES
            )
            await repository.update(attempt)

    async def _release(self, order_id: UUID) -> None:
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(order_id)
            if attempt is not None and attempt.payment_leased_until is not None:
                attempt.payment_leased_until = None
                await repository.update(attempt)

    async def _set_status(
        self,
        order_id: UUID,
        status: CJOrderAttemptStatus,
        *,
        amount_usd: Decimal | None = None,
        last_error: str | None = None,
    ) -> None:
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(order_id)
            if attempt is None or attempt.status not in CJOrderAttemptStatus.awaiting_payment():
                return
            attempt.status = status
            if amount_usd is not None:
                attempt.cj_order_amount_usd = amount_usd
            attempt.last_error = last_error[:2000] if last_error else None
            await repository.update(attempt)

    async def _note_error(self, order_id: UUID, message: str) -> None:
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(order_id)
            if attempt and attempt.status in CJOrderAttemptStatus.awaiting_payment():
                attempt.last_error = message[:2000]
                await repository.update(attempt)

    async def _record_paid(self, order_id: UUID, amount_usd: Decimal | None) -> CJOrderAttemptStatus:
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(order_id)
            if attempt is None:
                raise CJPaymentPending(f"CJ attempt for order {order_id} vanished")
            if attempt.status not in CJOrderAttemptStatus.awaiting_payment():
                # A concurrent run already recorded the outcome.
                return CJOrderAttemptStatus(attempt.status)
            attempt.status = CJOrderAttemptStatus.PAID
            attempt.paid_at = datetime.now(timezone.utc)
            attempt.last_error = None
            if amount_usd is not None:
                attempt.cj_order_amount_usd = amount_usd
            await repository.update(attempt)
            await OutboxEventService(OutboxRepository(session=session, model=OutboxEvent)).add_outbox_event(
                event_type=OrderEvents.CJ_ORDER_PAID,
                payload=CJOrderPaidEvent(
                    order_id=attempt.order_id,
                    user_id=attempt.user_id,
                    user_email=attempt.user_email,
                    cj_order_number=attempt.cj_order_number,
                    amount_usd=attempt.cj_order_amount_usd,
                ),
            )
        self.logger.info("Paid CJ order for local order %s (%s USD)", order_id, amount_usd)
        return CJOrderAttemptStatus.PAID

    async def _fail(self, order_id: UUID, reason: str) -> CJOrderAttemptStatus:
        """Give up on paying; cj.order.failed cancels the order and voids the card hold."""
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(order_id)
            if attempt is None or attempt.status not in CJOrderAttemptStatus.awaiting_payment():
                return CJOrderAttemptStatus(attempt.status) if attempt else CJOrderAttemptStatus.FAILED
            attempt.status = CJOrderAttemptStatus.FAILED
            attempt.last_error = reason[:2000]
            await repository.update(attempt)
            await OutboxEventService(OutboxRepository(session=session, model=OutboxEvent)).add_outbox_event(
                event_type=OrderEvents.CJ_ORDER_FAILED,
                payload=CJOrderFailedEvent(
                    service="supplier-service",
                    order_id=attempt.order_id,
                    user_id=attempt.user_id,
                    user_email=attempt.user_email,
                    reason=reason,
                ),
            )
        self.logger.error("CJ payment failed for order %s: %s", order_id, reason)
        return CJOrderAttemptStatus.FAILED


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
