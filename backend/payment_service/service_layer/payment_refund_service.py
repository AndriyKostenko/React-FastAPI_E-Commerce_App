"""Partial refunds, requested by order_service and carried out against Stripe."""

from enum import StrEnum
from logging import Logger

import stripe
from sqlalchemy.ext.asyncio import AsyncSession
from stripe import StripeClient

from database_layer.payment_repository import PaymentRefundRepository, PaymentRepository
from models.outbox_models import OutboxEvent
from models.payment_models import Payment, PaymentRefund
from service_layer.outbox_event_service import OutboxEventService
from shared.contracts.events import (
    PaymentRefundedEvent,
    PaymentRefundFailedEvent,
    PaymentRefundRequested,
)
from shared.database_layer.outbox_repository import OutboxRepository
from shared.enums.event_enums import PaymentEvents
from shared.enums.services_enums import Services
from shared.enums.status_enums import PaymentStatus
from shared.managers.database_session_manager import DatabaseSessionManager


class RefundStatus(StrEnum):
    PENDING = "pending"                  # reserved, Stripe not yet confirmed
    SUCCEEDED = "succeeded"              # refunded on Stripe
    REDUCED_CAPTURE = "reduced_capture"  # taken off before the card was captured
    FAILED = "failed"


# Stripe errors that mean "this refund will never work" rather than "try again".
_DEFINITIVE_STRIPE_ERRORS: tuple[type[stripe.StripeError], ...] = (
    stripe.InvalidRequestError,
    stripe.CardError,
)


class PaymentRefundService:
    """
    Gives back part of an order's payment, exactly once per refund id.

    - Captured: the amount is *reserved* on the payment in a short locked
      transaction, refunded on Stripe (idempotency key = refund id) with no
      transaction open, then settled — or un-reserved if Stripe refuses it.
      Concurrent refunds can therefore never exceed what was paid.
    - Only authorized: nothing has been charged, so the amount is taken off
      what will be captured (``capture_reduction_cents``). A reduction that
      would leave nothing to capture is refused: that is a cancellation.
    - An uncertain Stripe error (network, outage) is raised, so the command is
      retried; the row stays pending and the retry resumes it with the same
      idempotency key, so Stripe never refunds twice.
    """

    def __init__(self, database: DatabaseSessionManager, stripe_client: StripeClient, logger: Logger) -> None:
        self._database = database
        self._stripe = stripe_client
        self._logger = logger

    async def refund(self, command: PaymentRefundRequested) -> RefundStatus:
        reserved = await self._reserve(command)
        if reserved is None:
            return await self._status_of(command)
        payment_intent_id, amount_cents = reserved

        try:
            stripe_refund = await self._stripe.v1.refunds.create_async(
                {"payment_intent": payment_intent_id, "amount": amount_cents},
                options={"idempotency_key": f"payment_refund:partial:{command.refund_id}"},
            )
        except _DEFINITIVE_STRIPE_ERRORS as error:
            await self._fail_reserved(command, f"Stripe refused the refund: {error.user_message or error}")
            return RefundStatus.FAILED
        await self._settle(command, stripe_refund.id)
        return RefundStatus.SUCCEEDED

    # ------------------------------------------------------------------ phases

    async def _reserve(self, command: PaymentRefundRequested) -> tuple[str, int] | None:
        """
        Decide under the payment's row lock. Returns what to refund on Stripe,
        or None when the request was settled here (reduction, refusal, repeat).
        """
        async with self._database.transaction() as session:
            refunds = PaymentRefundRepository(session)
            existing = await refunds.get_by_id(command.refund_id)
            payment = await PaymentRepository(session).get_by_order_for_update(command.order_id)
            if existing is not None:
                # A redelivered command: finish a pending one, else nothing to do.
                if existing.status == RefundStatus.PENDING and payment is not None:
                    return payment.stripe_payment_intent_id, existing.amount_cents
                return None
            if payment is None:
                self._logger.error("Refund %s for order %s: no payment exists", command.refund_id, command.order_id)
                return None

            refusal = self._refusal(payment, command.amount_cents)
            if refusal is not None:
                await self._record(session, payment, command, RefundStatus.FAILED, failure_reason=refusal)
                await self._emit_failed(session, payment, command, refusal)
                return None

            if payment.status == PaymentStatus.AUTHORIZED:
                payment.capture_reduction_cents += command.amount_cents
                await self._record(session, payment, command, RefundStatus.REDUCED_CAPTURE)
                await self._emit_refunded(session, payment, command, applied_before_capture=True)
                return None

            payment.refunded_cents += command.amount_cents
            await self._record(session, payment, command, RefundStatus.PENDING)
            return payment.stripe_payment_intent_id, command.amount_cents

    @staticmethod
    def _refusal(payment: Payment, amount_cents: int) -> str | None:
        if payment.status == PaymentStatus.SUCCEEDED:
            if amount_cents > payment.refundable_cents:
                return f"{amount_cents} cents exceeds the {payment.refundable_cents} still refundable"
            return None
        if payment.status == PaymentStatus.AUTHORIZED:
            if amount_cents >= payment.refundable_cents:
                return "this would leave nothing to capture; cancel the order instead"
            return None
        return f"payment is {payment.status}; nothing can be refunded"

    async def _settle(self, command: PaymentRefundRequested, stripe_refund_id: str) -> None:
        async with self._database.transaction() as session:
            refund = await PaymentRefundRepository(session).get_by_id(command.refund_id)
            payment = await PaymentRepository(session).get_by_order_for_update(command.order_id)
            if refund is None or payment is None or refund.status != RefundStatus.PENDING:
                return
            refund.status = RefundStatus.SUCCEEDED
            refund.stripe_refund_id = stripe_refund_id
            if payment.refunded_cents >= payment.amount:
                payment.status = PaymentStatus.REFUNDED
            await session.flush()
            await self._emit_refunded(session, payment, command, applied_before_capture=False)
        self._logger.info("Refunded %s cents for order %s (refund %s)", command.amount_cents, command.order_id, command.refund_id)

    async def _fail_reserved(self, command: PaymentRefundRequested, reason: str) -> None:
        async with self._database.transaction() as session:
            refund = await PaymentRefundRepository(session).get_by_id(command.refund_id)
            payment = await PaymentRepository(session).get_by_order_for_update(command.order_id)
            if refund is None or payment is None or refund.status != RefundStatus.PENDING:
                return
            refund.status = RefundStatus.FAILED
            refund.failure_reason = reason
            payment.refunded_cents -= refund.amount_cents  # release the reservation
            await session.flush()
            await self._emit_failed(session, payment, command, reason)
        self._logger.error("Refund %s for order %s failed: %s", command.refund_id, command.order_id, reason)

    async def _status_of(self, command: PaymentRefundRequested) -> RefundStatus:
        async with self._database.transaction() as session:
            refund = await PaymentRefundRepository(session).get_by_id(command.refund_id)
        return RefundStatus(refund.status) if refund else RefundStatus.FAILED

    # ----------------------------------------------------------------- records

    @staticmethod
    async def _record(
        session: AsyncSession,
        payment: Payment,
        command: PaymentRefundRequested,
        status: RefundStatus,
        failure_reason: str | None = None,
    ) -> None:
        await PaymentRefundRepository(session).create(
            PaymentRefund(
                id=command.refund_id,
                payment_id=payment.id,
                amount_cents=command.amount_cents,
                reason=command.reason,
                status=status,
                failure_reason=failure_reason,
            )
        )

    @staticmethod
    async def _emit_refunded(
        session: AsyncSession, payment: Payment, command: PaymentRefundRequested, *, applied_before_capture: bool
    ) -> None:
        await OutboxEventService(OutboxRepository(session=session, model=OutboxEvent)).add_outbox_event(
            event_type=PaymentEvents.PAYMENT_REFUNDED,
            payload=PaymentRefundedEvent(
                service=Services.PAYMENT_SERVICE,
                order_id=payment.order_id,
                user_id=payment.user_id,
                user_email=payment.user_email,
                payment_intent_id=payment.stripe_payment_intent_id,
                amount=payment.amount,
                currency=payment.currency,
                refund_id=command.refund_id,
                refunded_amount_cents=command.amount_cents,
                applied_before_capture=applied_before_capture,
            ),
        )

    @staticmethod
    async def _emit_failed(
        session: AsyncSession, payment: Payment, command: PaymentRefundRequested, reason: str
    ) -> None:
        await OutboxEventService(OutboxRepository(session=session, model=OutboxEvent)).add_outbox_event(
            event_type=PaymentEvents.PAYMENT_REFUND_FAILED,
            payload=PaymentRefundFailedEvent(
                service=Services.PAYMENT_SERVICE,
                order_id=payment.order_id,
                user_id=payment.user_id,
                user_email=payment.user_email,
                payment_intent_id=payment.stripe_payment_intent_id,
                amount=payment.amount,
                currency=payment.currency,
                refund_id=command.refund_id,
                reason=reason,
            ),
        )
