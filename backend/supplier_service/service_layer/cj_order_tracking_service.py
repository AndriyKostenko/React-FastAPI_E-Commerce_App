"""Polls CJ Dropshipping for the fate of orders it has already accepted.

CJ pushes nothing back to us, so the only way to learn that a parcel shipped,
arrived, or was cancelled on CJ's side is to ask.  Each state change is written
to the local attempt row and to the transactional outbox in one transaction, so
a customer notification is never lost and never sent twice.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from logging import Logger
from typing import Any
from uuid import UUID

from database_layer.cj_order_attempt_repository import CJOrderAttemptRepository
from enums.cj_order_enums import CJOrderAttemptStatus, CJRemoteOrderStatus
from models.cj_order_attempt_models import CJOrderAttempt
from models.outbox_models import OutboxEvent
from service_layer.cj_api_client import CJDropshippingAPIClient, CJDropshippingAPIError
from service_layer.outbox_event_service import OutboxEventService
from shared.contracts.events import (
    CJOrderDeliveredEvent,
    CJOrderFailedEvent,
    CJOrderShippedEvent,
)
from shared.database_layer.outbox_repository import OutboxRepository
from shared.enums.event_enums import OrderEvents
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings


@dataclass(frozen=True, slots=True)
class TrackedOrder:
    """Detached snapshot of one leased attempt row.

    The row's lease is taken in a short transaction; the CJ call then runs with
    no session or lock held, so a slow CJ never pins a database connection.
    """

    order_id: UUID
    user_id: UUID
    user_email: str | None
    cj_order_number: str
    status: str


@dataclass(frozen=True, slots=True)
class CJOrderSnapshot:
    """What CJ currently reports about one order."""

    lifecycle: CJRemoteOrderStatus
    raw_status: str | None
    tracking_number: str | None
    logistic_name: str | None


@dataclass(frozen=True, slots=True)
class TrackingPollReport:
    """Outcome counts for one poll pass, surfaced to logs and task results."""

    polled: int = 0
    shipped: int = 0
    delivered: int = 0
    rejected: int = 0
    unchanged: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "polled": self.polled,
            "shipped": self.shipped,
            "delivered": self.delivered,
            "rejected": self.rejected,
            "unchanged": self.unchanged,
            "errors": self.errors,
        }


class CJRemoteOrderStatusMapper:
    """Maps CJ's order status vocabulary onto our own lifecycle.

    CJ's strings vary by API version and warehouse, so matching is done on the
    normalized token and unknown values map to UNKNOWN rather than guessing.
    """

    SHIPPED = frozenset(
        {"shipped", "shipping", "in_transit", "intransit", "dispatched", "sent"}
    )
    DELIVERED = frozenset({"delivered", "completed", "complete", "received", "signed"})
    CANCELLED = frozenset(
        {"cancelled", "canceled", "cancel", "rejected", "refunded", "closed", "deleted"}
    )
    PENDING = frozenset(
        {
            "created",
            "in_cart",
            "incart",
            "unpaid",
            "unshipped",
            "pending",
            "processing",
            "sourcing",
            "waiting",
        }
    )

    def map(self, raw_status: str | None) -> CJRemoteOrderStatus:
        token = self._normalize(raw_status)
        if not token:
            return CJRemoteOrderStatus.UNKNOWN
        if token in self.DELIVERED:
            return CJRemoteOrderStatus.DELIVERED
        if token in self.SHIPPED:
            return CJRemoteOrderStatus.SHIPPED
        if token in self.CANCELLED:
            return CJRemoteOrderStatus.CANCELLED
        if token in self.PENDING:
            return CJRemoteOrderStatus.PENDING
        return CJRemoteOrderStatus.UNKNOWN

    @staticmethod
    def _normalize(raw_status: str | None) -> str:
        if raw_status is None:
            return ""
        return str(raw_status).strip().lower().replace(" ", "_").replace("-", "_")


class CJOrderTrackingService:
    """Advances local CJ order state from what CJ reports, and notifies."""

    def __init__(
        self,
        settings: Settings,
        database: DatabaseSessionManager,
        api_client: CJDropshippingAPIClient,
        logger: Logger,
        status_mapper: CJRemoteOrderStatusMapper | None = None,
    ) -> None:
        self.settings: Settings = settings
        self.database: DatabaseSessionManager = database
        self.api_client: CJDropshippingAPIClient = api_client
        self.logger: Logger = logger
        self.status_mapper: CJRemoteOrderStatusMapper = (
            status_mapper or CJRemoteOrderStatusMapper()
        )

    async def poll_open_orders(self) -> TrackingPollReport:
        """Refresh every open CJ order that is due and emit any transitions."""
        tracked = await self.lease_due_orders()
        if not tracked:
            return TrackingPollReport()

        polled = shipped = delivered = rejected = unchanged = errors = 0
        for order in tracked:
            polled += 1
            try:
                snapshot = await self.fetch_snapshot(order)
            except CJDropshippingAPIError as exc:
                errors += 1
                self.logger.warning(
                    "CJ tracking poll failed for order %s (CJ %s): %s",
                    order.order_id,
                    order.cj_order_number,
                    exc,
                )
                continue

            try:
                outcome = await self.apply_snapshot(order, snapshot)
            except Exception:
                errors += 1
                self.logger.exception(
                    "Failed to apply CJ tracking state for order %s", order.order_id
                )
                continue

            match outcome:
                case CJOrderAttemptStatus.SHIPPED:
                    shipped += 1
                case CJOrderAttemptStatus.DELIVERED:
                    delivered += 1
                case CJOrderAttemptStatus.REJECTED:
                    rejected += 1
                case _:
                    unchanged += 1

        report = TrackingPollReport(
            polled=polled,
            shipped=shipped,
            delivered=delivered,
            rejected=rejected,
            unchanged=unchanged,
            errors=errors,
        )
        self.logger.info("CJ tracking poll finished: %s", report.as_dict())
        return report

    async def lease_due_orders(self) -> list[TrackedOrder]:
        """Claim due rows by stamping ``last_polled_at`` and detach them.

        Stamping inside the claiming transaction is what keeps a second poller
        from picking the same order up again while this one waits on CJ.
        """
        now = self._now()
        due_before = now - timedelta(
            minutes=self.settings.CJ_DROPSHIPPING_TRACKING_POLL_INTERVAL_MINUTES
        )
        created_after = now - timedelta(
            days=self.settings.CJ_DROPSHIPPING_TRACKING_MAX_AGE_DAYS
        )

        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempts = await repository.claim_due_for_tracking(
                due_before=due_before,
                created_after=created_after,
                limit=self.settings.CJ_DROPSHIPPING_TRACKING_POLL_BATCH_SIZE,
            )
            leased: list[TrackedOrder] = []
            for attempt in attempts:
                attempt.last_polled_at = now
                leased.append(
                    TrackedOrder(
                        order_id=attempt.order_id,
                        user_id=attempt.user_id,
                        user_email=attempt.user_email,
                        cj_order_number=attempt.cj_order_number or "",
                        status=attempt.status,
                    )
                )
            # Flush the lease before the transaction ends so a concurrent
            # poller sees the new last_polled_at and skips these rows.
            await session.flush()
            return leased

    async def fetch_snapshot(self, order: TrackedOrder) -> CJOrderSnapshot:
        """Read CJ's current view of one order."""
        response = await self.api_client.get_order_detail(order.cj_order_number)
        return self.parse_snapshot(response)

    def parse_snapshot(self, response: dict[str, Any]) -> CJOrderSnapshot:
        """Turn a getOrderDetail body into a lifecycle snapshot."""
        data = response.get("data")
        if isinstance(data, list):
            data = data[0] if data else None
        if not isinstance(data, dict):
            return CJOrderSnapshot(
                lifecycle=CJRemoteOrderStatus.UNKNOWN,
                raw_status=None,
                tracking_number=None,
                logistic_name=None,
            )

        raw_status = data.get("orderStatus") or data.get("status")
        tracking_number = (
            data.get("trackNumber")
            or data.get("trackingNumber")
            or data.get("logisticTrackNumber")
        )
        return CJOrderSnapshot(
            lifecycle=self.status_mapper.map(raw_status),
            raw_status=str(raw_status) if raw_status else None,
            tracking_number=str(tracking_number) if tracking_number else None,
            logistic_name=(
                str(data["logisticName"]) if data.get("logisticName") else None
            ),
        )

    async def apply_snapshot(
        self, order: TrackedOrder, snapshot: CJOrderSnapshot
    ) -> CJOrderAttemptStatus | None:
        """Persist the snapshot and enqueue any resulting customer events.

        Returns the new attempt status, or ``None`` when nothing changed.
        """
        async with self.database.transaction() as session:
            repository = CJOrderAttemptRepository(session)
            attempt = await repository.get_for_update(order.order_id)
            if attempt is None:
                self.logger.warning(
                    "CJ attempt row for order %s vanished mid-poll", order.order_id
                )
                return None
            if attempt.status in CJOrderAttemptStatus.terminal():
                return None

            attempt.cj_order_status = snapshot.raw_status
            if snapshot.tracking_number:
                attempt.tracking_number = snapshot.tracking_number
            if snapshot.logistic_name:
                attempt.logistic_name = snapshot.logistic_name

            outbox = OutboxEventService(
                OutboxRepository(session=session, model=OutboxEvent)
            )
            new_status = await self._transition(attempt, snapshot, outbox)
            await repository.update(attempt)
            return new_status

    async def _transition(
        self,
        attempt: CJOrderAttempt,
        snapshot: CJOrderSnapshot,
        outbox: OutboxEventService,
    ) -> CJOrderAttemptStatus | None:
        """Move ``attempt`` to the state CJ reports, queuing customer events."""
        match snapshot.lifecycle:
            case CJRemoteOrderStatus.CANCELLED:
                return await self._mark_rejected(attempt, snapshot, outbox)
            case CJRemoteOrderStatus.DELIVERED:
                return await self._mark_delivered(attempt, outbox)
            case CJRemoteOrderStatus.SHIPPED:
                return await self._mark_shipped(attempt, outbox)
            case _:
                return None

    async def _mark_shipped(
        self, attempt: CJOrderAttempt, outbox: OutboxEventService
    ) -> CJOrderAttemptStatus | None:
        if attempt.status == CJOrderAttemptStatus.SHIPPED:
            return None
        if not attempt.tracking_number:
            # CJ reports SHIPPED before assigning a tracking number often
            # enough that notifying now would send a useless email.
            self.logger.info(
                "CJ order %s is shipped but has no tracking number yet",
                attempt.cj_order_number,
            )
            return None

        attempt.status = CJOrderAttemptStatus.SHIPPED
        attempt.shipped_at = attempt.shipped_at or self._now()
        await self._queue_shipped_event(attempt, outbox)
        return CJOrderAttemptStatus.SHIPPED

    async def _mark_delivered(
        self, attempt: CJOrderAttempt, outbox: OutboxEventService
    ) -> CJOrderAttemptStatus:
        # A parcel can be delivered between two polls. Emitting the shipped
        # event too keeps the customer's order history complete.
        if attempt.status != CJOrderAttemptStatus.SHIPPED and attempt.tracking_number:
            attempt.shipped_at = attempt.shipped_at or self._now()
            await self._queue_shipped_event(attempt, outbox)

        attempt.status = CJOrderAttemptStatus.DELIVERED
        attempt.delivered_at = attempt.delivered_at or self._now()
        if self._can_notify(attempt):
            await outbox.add_outbox_event(
                event_type=OrderEvents.CJ_ORDER_DELIVERED,
                payload=CJOrderDeliveredEvent(
                    service="supplier-service",
                    order_id=attempt.order_id,
                    user_id=attempt.user_id,
                    user_email=attempt.user_email,
                    cj_order_number=attempt.cj_order_number or "",
                    tracking_number=attempt.tracking_number,
                    delivered_at=attempt.delivered_at,
                ),
            )
        return CJOrderAttemptStatus.DELIVERED

    async def _mark_rejected(
        self,
        attempt: CJOrderAttempt,
        snapshot: CJOrderSnapshot,
        outbox: OutboxEventService,
    ) -> CJOrderAttemptStatus:
        reason = (
            f"CJ cancelled order {attempt.cj_order_number} "
            f"(CJ status: {snapshot.raw_status or 'unknown'})"
        )
        attempt.status = CJOrderAttemptStatus.REJECTED
        attempt.last_error = reason[:2000]
        self.logger.error("CJ rejected an accepted order: %s", reason)

        if self._can_notify(attempt):
            # cj.order.failed is the saga's compensation trigger: order_service
            # cancels the order, which makes payment_service refund it.
            await outbox.add_outbox_event(
                event_type=OrderEvents.CJ_ORDER_FAILED,
                payload=CJOrderFailedEvent(
                    service="supplier-service",
                    order_id=attempt.order_id,
                    user_id=attempt.user_id,
                    user_email=attempt.user_email,
                    reason=reason,
                ),
            )
        return CJOrderAttemptStatus.REJECTED

    async def _queue_shipped_event(
        self, attempt: CJOrderAttempt, outbox: OutboxEventService
    ) -> None:
        if not self._can_notify(attempt) or not attempt.tracking_number:
            return
        await outbox.add_outbox_event(
            event_type=OrderEvents.CJ_ORDER_SHIPPED,
            payload=CJOrderShippedEvent(
                service="supplier-service",
                order_id=attempt.order_id,
                user_id=attempt.user_id,
                user_email=attempt.user_email,
                cj_order_number=attempt.cj_order_number or "",
                tracking_number=attempt.tracking_number,
                logistic_name=attempt.logistic_name,
                tracking_url=self.build_tracking_url(attempt.tracking_number),
                shipped_at=attempt.shipped_at or self._now(),
            ),
        )

    def build_tracking_url(self, tracking_number: str | None) -> str | None:
        template = self.settings.CJ_DROPSHIPPING_TRACKING_URL_TEMPLATE
        if not tracking_number or not template:
            return None
        try:
            return template.format(tracking_number=tracking_number)
        except (IndexError, KeyError):
            self.logger.warning(
                "CJ_DROPSHIPPING_TRACKING_URL_TEMPLATE is malformed: %s", template
            )
            return None

    def _can_notify(self, attempt: CJOrderAttempt) -> bool:
        """Customer events carry an email; rows predating it cannot be sent."""
        if attempt.user_email:
            return True
        self.logger.error(
            "CJ attempt for order %s has no user_email; skipping customer event",
            attempt.order_id,
        )
        return False

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
