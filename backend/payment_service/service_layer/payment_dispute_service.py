"""Chargebacks: recorded, the order flagged, an admin told. No automatic action."""

from datetime import UTC, datetime
from logging import Logger
from typing import Any

from database_layer.payment_repository import PaymentDisputeRepository, PaymentRepository
from models.payment_models import PaymentDispute
from service_layer.outbox_event_service import OutboxEventService
from shared.contracts.events import PaymentDisputeEvent
from shared.enums.event_enums import PaymentEvents
from shared.enums.services_enums import Services


class PaymentDisputeService:
    """
    Keeps one row per Stripe dispute, updated as Stripe reports changes.

    Opening and closing are published (payment.dispute_opened / _closed) so
    order-service flags the order and notification-service alerts an admin —
    evidence is due by a deadline, and missing it loses the dispute. Updates in
    between only refresh the row. A repeated webhook changes nothing.
    """

    def __init__(
        self,
        payment_repository: PaymentRepository,
        dispute_repository: PaymentDisputeRepository,
        outbox_event_service: OutboxEventService,
        logger: Logger,
    ) -> None:
        self._payments = payment_repository
        self._disputes = dispute_repository
        self._outbox = outbox_event_service
        self._logger = logger

    async def opened(self, stripe_event_data: dict[str, Any]) -> None:
        await self._record(stripe_event_data["object"], PaymentEvents.PAYMENT_DISPUTE_OPENED)

    async def updated(self, stripe_event_data: dict[str, Any]) -> None:
        await self._record(stripe_event_data["object"], event_type=None)

    async def closed(self, stripe_event_data: dict[str, Any]) -> None:
        await self._record(stripe_event_data["object"], PaymentEvents.PAYMENT_DISPUTE_CLOSED)

    async def _record(self, dispute: dict[str, Any], event_type: PaymentEvents | None) -> None:
        payment = await self._payments.get_by_field("stripe_payment_intent_id", dispute.get("payment_intent") or "")
        existing = await self._disputes.get_by_field("stripe_dispute_id", dispute["id"])
        status = str(dispute.get("status") or "unknown")
        if existing is not None and existing.status == status:
            return  # a repeated webhook: already recorded
        due = (dispute.get("evidence_details") or {}).get("due_by")
        evidence_due_by = datetime.fromtimestamp(due, UTC) if due else None

        if existing is None:
            await self._disputes.create(PaymentDispute(
                stripe_dispute_id=dispute["id"],
                payment_id=payment.id if payment else None,
                amount_cents=int(dispute.get("amount") or 0),
                currency=str(dispute.get("currency") or ""),
                reason=str(dispute.get("reason") or "unknown"),
                status=status,
                evidence_due_by=evidence_due_by,
            ))
        else:
            existing.status = status
            existing.evidence_due_by = evidence_due_by or existing.evidence_due_by
            await self._disputes.update(existing)

        self._logger.critical(
            "DISPUTE %s on payment %s (order %s): %s cents, reason %s, status %s, evidence due %s",
            dispute["id"], dispute.get("payment_intent"), payment.order_id if payment else "unknown",
            dispute.get("amount"), dispute.get("reason"), status, evidence_due_by,
        )
        if event_type is None or payment is None:
            return
        await self._outbox.add_outbox_event(
            event_type=event_type,
            payload=PaymentDisputeEvent(
                service=Services.PAYMENT_SERVICE,
                event_type=event_type,
                order_id=payment.order_id,
                user_id=payment.user_id,
                user_email=payment.user_email,
                payment_intent_id=payment.stripe_payment_intent_id,
                amount=payment.amount,
                currency=payment.currency,
                dispute_id=dispute["id"],
                disputed_amount_cents=int(dispute.get("amount") or 0),
                reason=str(dispute.get("reason") or "unknown"),
                dispute_status=status,
                evidence_due_by=evidence_due_by,
            ),
        )
