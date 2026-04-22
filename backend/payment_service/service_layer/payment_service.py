from uuid import UUID
from typing import Any

import stripe
from sqlalchemy.exc import IntegrityError

from database_layer.payment_repository import PaymentRepository
from models.payment_models import Payment
from service_layer.outbox_event_service import OutboxEventService
from exceptions.payment_exceptions import (
    PaymentNotFoundError,
    PaymentsNotFoundError,
    DuplicatePaymentIntentError,
    PaymentCreationError,
    InvalidStripeWebhookSignature,
    StripePaymentIntentCreationError,
)
from shared.schemas.event_schemas import PaymentSucceededEvent, PaymentFailedEvent
from shared.enums.event_enums import PaymentEvents
from shared.enums.status_enums import PaymentStatus
from shared.enums.services_enums import Services
from shared.settings import Settings


class PaymentService:
    """Business logic layer for payment management using Stripe."""

    def __init__(
        self,
        repository: PaymentRepository,
        outbox_event_service: OutboxEventService,
        settings: Settings,
    ) -> None:
        self.repository: PaymentRepository = repository
        self.outbox_event_service: OutboxEventService = outbox_event_service
        self._stripe = stripe
        self._stripe.api_key = settings.STRIPE_SECRET_KEY
        self._webhook_secret: str = settings.STRIPE_WEBHOOK_SECRET

    async def create_payment_intent(
        self,
        order_id: UUID,
        user_id: UUID,
        user_email: str,
        amount: int,
        currency: str,
    ) -> dict[str, Any]:
        """
        Create a Stripe PaymentIntent and persist a pending Payment record.

        Returns a dict with client_secret and stripe_payment_intent_id so the
        frontend can confirm the payment via Stripe.js.
        """
        try:
            intent = self._stripe.PaymentIntent.create(
                amount=amount,          # in cents
                currency=currency,
                metadata={"order_id": str(order_id), "user_id": str(user_id)},
                idempotency_key=str(order_id),  # safe to retry for same order
            )
        except self._stripe.StripeError as exc:
            raise StripePaymentIntentCreationError(detail=str(exc)) from exc

        try:
            async with self.repository.session.begin_nested():
                payment = await self.repository.create(
                    Payment(
                        order_id=order_id,
                        user_id=user_id,
                        user_email=user_email,
                        stripe_payment_intent_id=intent.id,
                        amount=amount,
                        currency=currency,
                        status=PaymentStatus.PENDING,
                    )
                )
        except IntegrityError:
            raise DuplicatePaymentIntentError(payment_intent_id=intent.id)

        if not payment:
            raise PaymentCreationError()

        return {
            "client_secret": intent.client_secret,
            "stripe_payment_intent_id": intent.id,
            "payment_id": str(payment.id),
        }

    def construct_webhook_event(self, payload: bytes, stripe_signature: str) -> Any:
        """Verify and construct a Stripe webhook event. Raises InvalidStripeWebhookSignature on failure."""
        try:
            return self._stripe.Webhook.construct_event(
                payload, stripe_signature, self._webhook_secret
            )
        except (self._stripe.SignatureVerificationError, ValueError):
            raise InvalidStripeWebhookSignature()

    async def handle_payment_intent_succeeded(self, stripe_event_data: dict[str, Any]) -> None:
        """
        Handle payment_intent.succeeded webhook event.

        Updates the Payment record to 'succeeded' and writes a payment.succeeded
        outbox event for downstream services (order service, notifications).
        """
        intent = stripe_event_data["object"]
        payment_intent_id: str = intent["id"]
        metadata: dict = intent.get("metadata", {})

        payment = await self.repository.get_by_field(
            field_name="stripe_payment_intent_id", value=payment_intent_id
        )
        if not payment:
            raise PaymentNotFoundError(payment_id=payment_intent_id)  # type: ignore[arg-type]

        async with self.repository.session.begin_nested():
            await self.repository.update_by_id(
                item_id=payment.id,
                data={"status": PaymentStatus.SUCCEEDED},
            )
            await self.outbox_event_service.add_outbox_event(
                event_type=PaymentEvents.PAYMENT_SUCCEEDED,
                payload=PaymentSucceededEvent(
                    service=Services.PAYMENT_SERVICE,
                    event_type=PaymentEvents.PAYMENT_SUCCEEDED,
                    order_id=metadata.get("order_id") or payment.order_id,
                    user_id=metadata.get("user_id") or payment.user_id,
                    user_email=payment.user_email,
                    payment_intent_id=payment_intent_id,
                    amount=payment.amount,
                    currency=payment.currency,
                ),
            )

    async def handle_payment_intent_failed(self, stripe_event_data: dict[str, Any]) -> None:
        """
        Handle payment_intent.payment_failed webhook event.

        Updates the Payment record to 'failed' and writes a payment.failed
        outbox event so upstream services can cancel the order.
        """
        intent = stripe_event_data["object"]
        payment_intent_id: str = intent["id"]
        metadata: dict = intent.get("metadata", {})
        failure_reason: str = (
            intent.get("last_payment_error", {}) or {}
        ).get("message", "Unknown error")

        payment = await self.repository.get_by_field(
            field_name="stripe_payment_intent_id", value=payment_intent_id
        )
        if not payment:
            raise PaymentNotFoundError(payment_id=payment_intent_id)  # type: ignore[arg-type]

        async with self.repository.session.begin_nested():
            await self.repository.update_by_id(
                item_id=payment.id,
                data={"status": PaymentStatus.FAILED, "failure_reason": failure_reason},
            )
            await self.outbox_event_service.add_outbox_event(
                event_type=PaymentEvents.PAYMENT_FAILED,
                payload=PaymentFailedEvent(
                    service=Services.PAYMENT_SERVICE,
                    event_type=PaymentEvents.PAYMENT_FAILED,
                    order_id=metadata.get("order_id") or payment.order_id,
                    user_id=metadata.get("user_id") or payment.user_id,
                    user_email=payment.user_email,
                    payment_intent_id=payment_intent_id,
                    amount=payment.amount,
                    currency=payment.currency,
                    reason=failure_reason,
                ),
            )

    async def get_payment_by_id(self, payment_id: UUID) -> Payment:
        payment = await self.repository.get_by_id(payment_id)
        if not payment:
            raise PaymentNotFoundError(payment_id)
        return payment

    async def get_payments(self) -> list[Payment]:
        payments = await self.repository.get_all()
        if not payments:
            raise PaymentsNotFoundError()
        return payments
