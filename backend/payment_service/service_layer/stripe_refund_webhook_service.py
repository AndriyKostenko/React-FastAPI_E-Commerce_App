"""Refunds Stripe reports through ``charge.refund.updated``."""

from logging import Logger
from typing import Any
from uuid import uuid4

from database_layer.payment_repository import PaymentRefundRepository, PaymentRepository
from models.payment_models import Payment, PaymentRefund
from service_layer.outbox_event_service import OutboxEventService
from service_layer.payment_refund_service import RefundStatus
from service_layer.refund_metadata import AppRefundMetadata
from shared.contracts.events import PaymentRefundedEvent, RefundScope
from shared.enums.event_enums import PaymentEvents
from shared.enums.services_enums import Services
from shared.enums.status_enums import PaymentStatus


class StripeRefundWebhookService:
    """
    Records the refunds made outside this service, e.g. in the Stripe dashboard.

    Our own refunds carry ``AppRefundMetadata`` and are recorded by the path
    that made them (a partial refund by ``PaymentRefundService``, a whole one
    by ``PaymentService``), so their webhook changes nothing here. Marking the
    whole payment refunded on any refund, as this used to, made every partial
    refund look like a full one: the customer was told so, and every later
    refund was refused.

    A refund from elsewhere is recorded once (keyed by Stripe's refund id) as
    money given back after capture. The payment becomes ``refunded`` only once
    nothing is left to refund.
    """

    EXTERNAL_REASON = "Refunded outside the app (Stripe dashboard)"

    def __init__(
        self,
        payment_repository: PaymentRepository,
        refund_repository: PaymentRefundRepository,
        outbox_event_service: OutboxEventService,
        logger: Logger,
    ) -> None:
        self._payments = payment_repository
        self._refunds = refund_repository
        self._outbox = outbox_event_service
        self._logger = logger

    async def refund_updated(self, stripe_event_data: dict[str, Any]) -> None:
        refund: dict[str, Any] = stripe_event_data["object"]
        if refund.get("status") != "succeeded":
            return  # pending / failed / cancelled refunds moved no money
        if AppRefundMetadata.is_ours(refund.get("metadata")):
            return  # recorded by the path that created it

        payment_intent_id = str(refund.get("payment_intent") or "")
        payment = await self._payments.get_by_intent_for_update(payment_intent_id)
        if payment is None:
            # Raising would make Stripe redeliver for days over a charge this
            # service never made (the account may serve other integrations).
            self._logger.warning(
                "Refund %s on payment intent %s: no such payment here; ignored",
                refund.get("id"), payment_intent_id,
            )
            return
        if await self._refunds.get_by_stripe_refund_id(str(refund["id"])) is not None:
            return  # a redelivered webhook, or a refund recorded before the marker existed
        if payment.status != PaymentStatus.SUCCEEDED:
            self._logger.warning(
                "Refund %s for order %s arrived while the payment is %s; nothing recorded",
                refund["id"], payment.order_id, payment.status,
            )
            return

        await self._record_external(payment, refund)

    async def _record_external(self, payment: Payment, refund: dict[str, Any]) -> None:
        amount_cents = int(refund.get("amount") or 0)
        recorded = await self._refunds.create(
            PaymentRefund(
                id=uuid4(),
                payment_id=payment.id,
                amount_cents=amount_cents,
                reason=self.EXTERNAL_REASON,
                status=RefundStatus.SUCCEEDED,
                stripe_refund_id=str(refund["id"]),
            )
        )
        # Stripe never refunds more than it captured; the cap only keeps the
        # books consistent if a refund was somehow missed earlier.
        captured = payment.amount - payment.capture_reduction_cents
        payment.refunded_cents = min(payment.refunded_cents + amount_cents, captured)
        whole = payment.refundable_cents <= 0
        if whole:
            payment.status = PaymentStatus.REFUNDED
        await self._payments.update(payment)

        self._logger.critical(
            "Refund %s of %s cents for order %s was made outside the app; recorded here, "
            "but order-service has no record of which lines it covers",
            refund["id"], amount_cents, payment.order_id,
        )
        if payment.tax_calculation_id:
            self._logger.critical(
                "TAX RECORD REQUIRED for order %s: refund %s was made outside the app, "
                "so no tax reversal was recorded; record it in the Stripe dashboard",
                payment.order_id, refund["id"],
            )

        await self._outbox.add_outbox_event(
            event_type=PaymentEvents.PAYMENT_REFUNDED,
            payload=PaymentRefundedEvent(
                service=Services.PAYMENT_SERVICE,
                order_id=payment.order_id,
                user_id=payment.user_id,
                user_email=payment.user_email,
                payment_intent_id=payment.stripe_payment_intent_id,
                amount=payment.amount,
                currency=payment.currency,
                # A partial refund is announced as one; order-service ignores
                # a refund id it did not issue.
                refund_id=None if whole else recorded.id,
                refunded_amount_cents=amount_cents,
                refund_scope=RefundScope.after(
                    refunded_total_cents=payment.refunded_cents,
                    this_refund_cents=amount_cents,
                    left_cents=payment.refundable_cents,
                ),
            ),
        )
