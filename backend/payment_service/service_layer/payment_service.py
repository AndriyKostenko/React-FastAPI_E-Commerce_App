from uuid import UUID
from typing import Any

from stripe import StripeClient, StripeError, SignatureVerificationError, Event as StripeEvent
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
    PaymentRefundError,
)
from shared.schemas.event_schemas import PaymentSucceededEvent, PaymentFailedEvent, PaymentRefundedEvent
from shared.enums.event_enums import PaymentEvents
from shared.enums.status_enums import PaymentStatus
from shared.enums.services_enums import Services
from shared.settings import Settings


class PaymentService:
    """Business logic layer for payment management using Stripe."""

    def __init__(self,repository: PaymentRepository,outbox_event_service: OutboxEventService, settings: Settings) -> None:
        self.repository: PaymentRepository = repository
        self.outbox_event_service: OutboxEventService = outbox_event_service
        self.webhook_endpoint : str= settings.FULL_STRIPE_WEBHOOK_ENDPOINT
        self._webhook_secret: str = settings.STRIPE_WEBHOOK_SECRET
        self._stripe_api_key: str = settings.STRIPE_SECRET_KEY
        self._stripe: StripeClient = StripeClient(api_key=self._stripe_api_key)


    async def create_payment_intent(self,
                                    order_id: UUID,
                                    user_id: UUID,
                                    user_email: str,
                                    amount: int,
                                    currency: str) -> dict[str, Any]:
        """
        Create a Stripe PaymentIntent and persist a pending Payment record.

        Returns a dict with client_secret and stripe_payment_intent_id so the
        frontend can confirm the payment via Stripe.js.
        """
        try:
            intent = self._stripe.v1.payment_intents.create({
                "amount": amount,
                "currency": currency,
                "metadata": {
                    "order_id": str(order_id),
                    "user_id": str(user_id),
                    "user_email": user_email,
                },
                "automatic_payment_methods": {"enabled": True},
            })
        except StripeError as exc:
            raise StripePaymentIntentCreationError(detail=str(exc))

        try:
            async with self.repository.session.begin_nested():
                # creates a **savepoint** — a checkpoint *within* the outer transactio
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

    def construct_webhook_event(self, payload: bytes, stripe_signature: str) -> StripeEvent:
        """Verify and construct a Stripe webhook event. Raises InvalidStripeWebhookSignature on failure."""
        try:
            return self._stripe.construct_event(payload=payload,
                                                sig_header=stripe_signature,
                                                secret=self._webhook_secret)
        except (SignatureVerificationError, ValueError):
            raise InvalidStripeWebhookSignature()

    async def handle_payment_intent_succeeded(self, stripe_event_data: dict[str, Any]) -> None:
        """
        Handle payment_intent.succeeded webhook event.

        Updates the Payment record to 'succeeded' and writes a payment.succeeded
        outbox event for downstream services (order service, notifications).
        """
        intent = stripe_event_data["object"]
        payment_intent_id: str = intent["id"]
        metadata: dict[str, Any] = intent.get("metadata", {})

        payment = await self.repository.get_by_field(
            field_name="stripe_payment_intent_id", value=payment_intent_id
        )
        if not payment:
            raise PaymentNotFoundError(payment_id=payment_intent_id)

        async with self.repository.session.begin_nested():
            _ = await self.repository.update_by_id(
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
        metadata: dict[str, Any] = intent.get("metadata", {})
        failure_reason: str = (
            intent.get("last_payment_error", {}) or {}
        ).get("message", "Unknown error")

        payment = await self.repository.get_by_field(
            field_name="stripe_payment_intent_id", value=payment_intent_id
        )
        if not payment:
            raise PaymentNotFoundError(payment_id=payment_intent_id)

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

    async def refund_payment(self, order_id: UUID) -> Payment | None:
        """
        Issue a Stripe refund for a previously succeeded payment tied to the given order.

        Steps:
        1. Look up the payment record by order_id.
        2. Skip silently if no payment exists or payment has not succeeded.
        3. Call Stripe refund API.
        4. Update local status to REFUNDED and write a payment.refunded outbox event.
        """
        payment = await self.repository.get_by_field(field_name="order_id", value=order_id)
        if not payment:
            # No payment record exists for this order (e.g. order cancelled before a
            # payment intent was ever created). Nothing to refund — log and return.
            self.logger.info(
                f"No payment record found for order {order_id} during refund — skipping"
            )
            return None

        if payment.status != PaymentStatus.SUCCEEDED:
            # Nothing to refund — payment was never charged or already refunded/failed
            return payment

        try:
            self._stripe.v1.refunds.create(
                {"payment_intent": payment.stripe_payment_intent_id}
            )
        except StripeError as exc:
            raise PaymentRefundError(detail=str(exc))

        async with self.repository.session.begin_nested():
            updated_payment = await self.repository.update_by_id(
                item_id=payment.id,
                data={"status": PaymentStatus.REFUNDED},
            )
            await self.outbox_event_service.add_outbox_event(
                event_type=PaymentEvents.PAYMENT_REFUNDED,
                payload=PaymentRefundedEvent(
                    service=Services.PAYMENT_SERVICE,
                    event_type=PaymentEvents.PAYMENT_REFUNDED,
                    order_id=payment.order_id,
                    user_id=payment.user_id,
                    user_email=payment.user_email,
                    payment_intent_id=payment.stripe_payment_intent_id,
                    amount=payment.amount,
                    currency=payment.currency,
                ),
            )

        return updated_payment

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
