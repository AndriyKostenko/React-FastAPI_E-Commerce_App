from logging import Logger
from uuid import UUID
from typing import Any

from fastapi import Request
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
    PaymentAlreadyFinalizedError,
    InvalidStripeWebhookSignature,
    StripePaymentIntentCreationError,
    PaymentRefundError,
    PaymentDataIsNotProvided
)
from shared.schemas.event_schemas import (
    PaymentSucceededEvent,
    PaymentFailedEvent,
    PaymentRefundedEvent,
    PaymentCancelledEvent,
)
from shared.enums.event_enums import PaymentEvents
from shared.enums.status_enums import PaymentStatus
from shared.enums.services_enums import Services
from shared.settings import Settings


class PaymentService:
    """Business logic layer for payment management using Stripe."""

    def __init__(self,
                repository: PaymentRepository,
                outbox_event_service: OutboxEventService,
                settings: Settings,
                logger: Logger) -> None:
        self.logger: Logger = logger
        self.settings: Settings = settings
        self.repository: PaymentRepository = repository
        self.outbox_event_service: OutboxEventService = outbox_event_service
        self.webhook_endpoint : str= self.settings.FULL_STRIPE_WEBHOOK_ENDPOINT
        self._webhook_secret: str = self.settings.STRIPE_WEBHOOK_SECRET
        self._stripe_api_key: str = self.settings.STRIPE_TEST_SECRET_KEY
        self._stripe: StripeClient = StripeClient(api_key=self._stripe_api_key)

    def _create_intent_idempotency_key(self, order_id: UUID) -> str:
        return f"payment_intent:create:{order_id}"

    def _create_stripe_payment_intent(
        self,
        order_id: UUID,
        user_id: UUID,
        user_email: str,
        amount: int,
        currency: str,
    ) -> Any:
        return self._stripe.v1.payment_intents.create(
            {
                "amount": amount,
                "currency": currency,
                "metadata": {
                    "order_id": str(order_id),
                    "user_id": str(user_id),
                    "user_email": user_email,
                },
                "automatic_payment_methods": {"enabled": True},
            },
            options={"idempotency_key": self._create_intent_idempotency_key(order_id)},
        )

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
            existing_payment = await self.repository.get_by_field(field_name="order_id", value=order_id)

            if existing_payment and existing_payment.status in {PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED}:
                raise PaymentAlreadyFinalizedError(order_id=order_id)

            if existing_payment and existing_payment.status == PaymentStatus.PENDING:
                existing_intent = self._stripe.v1.payment_intents.retrieve(existing_payment.stripe_payment_intent_id)
                return {
                    "client_secret": existing_intent.client_secret,
                    "stripe_payment_intent_id": existing_payment.stripe_payment_intent_id,
                    "payment_id": str(existing_payment.id),
                    "order_id": str(order_id),
                }

            intent = self._create_stripe_payment_intent(
                order_id=order_id,
                user_id=user_id,
                user_email=user_email,
                amount=amount,
                currency=currency,
            )
        except StripeError as exc:
            raise StripePaymentIntentCreationError(detail=str(exc))

        try:
            if existing_payment and existing_payment.status in {PaymentStatus.FAILED, PaymentStatus.CANCELLED}:
                async with self.repository.session.begin_nested():
                    payment = await self.repository.update_by_id(
                        item_id=existing_payment.id,
                        data={
                            "stripe_payment_intent_id": intent.id,
                            "amount": amount,
                            "currency": currency,
                            "status": PaymentStatus.PENDING,
                            "failure_reason": None,
                            "user_email": user_email,
                        },
                    )
            else:
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
            "order_id": str(order_id),
        }

    async def construct_webhook_event(self, request: Request) -> StripeEvent:
        """Verify and construct a Stripe webhook event. Raises InvalidStripeWebhookSignature on failure."""
        payload: bytes = await request.body()
        if not payload:
            raise PaymentDataIsNotProvided()
        stripe_signature: str = request.headers.get("stripe-signature", "")
        if not stripe_signature:
            raise InvalidStripeWebhookSignature()
        try:
            return self._stripe.construct_event(payload=payload,
                                                sig_header=stripe_signature,
                                                secret=self._webhook_secret)
        except (SignatureVerificationError, ValueError):
            raise

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

    async def handle_payment_refund(self, order_id: UUID) -> Payment | None:
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
            _ = self._stripe.v1.refunds.create(
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

    async def handle_charge_refund_updated(self, stripe_event_data: dict[str, Any]) -> None:
        """
        Handle charge.refund.updated webhook event.

        Stripe fires this when a refund transitions to a terminal state.
        Only acts when refund status is 'succeeded' and the payment is not
        already marked as REFUNDED (guards against double-processing if
        handle_payment_refund() already updated the record synchronously).
        """
        refund = stripe_event_data["object"]
        refund_status: str = refund.get("status", "")
        payment_intent_id: str = refund.get("payment_intent", "")

        if refund_status != "succeeded":
            # Pending / failed / cancelled refunds are not actionable here
            return

        payment = await self.repository.get_by_field(
            field_name="stripe_payment_intent_id", value=payment_intent_id
        )
        if not payment:
            raise PaymentNotFoundError(payment_id=payment_intent_id)

        if payment.status == PaymentStatus.REFUNDED:
            # Already handled (e.g. by handle_payment_refund synchronous path)
            return

        async with self.repository.session.begin_nested():
            _ = await self.repository.update_by_id(
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
                    payment_intent_id=payment_intent_id,
                    amount=refund.get("amount", payment.amount),
                    currency=payment.currency,
                ),
            )

    async def handle_payment_intent_cancelled(self, stripe_event_data: dict[str, Any]) -> None:
        """
        Handle payment_intent.canceled webhook event.

        Stripe fires this when a PaymentIntent is cancelled (e.g. expired,
        manually cancelled, or superseded). Treated as a payment failure so
        the order SAGA can compensate.
        """
        intent = stripe_event_data["object"]
        payment_intent_id: str = intent["id"]
        metadata: dict[str, Any] = intent.get("metadata", {})
        cancellation_reason: str = intent.get("cancellation_reason") or "Payment intent cancelled"

        payment = await self.repository.get_by_field(
            field_name="stripe_payment_intent_id", value=payment_intent_id
        )
        if not payment:
            raise PaymentNotFoundError(payment_id=payment_intent_id)

        async with self.repository.session.begin_nested():
            _ = await self.repository.update_by_id(
                item_id=payment.id,
                data={"status": PaymentStatus.CANCELLED, "failure_reason": cancellation_reason},
            )
            await self.outbox_event_service.add_outbox_event(
                event_type=PaymentEvents.PAYMENT_CANCELLED,
                payload=PaymentCancelledEvent(
                    service=Services.PAYMENT_SERVICE,
                    event_type=PaymentEvents.PAYMENT_CANCELLED,
                    order_id=metadata.get("order_id") or payment.order_id,
                    user_id=metadata.get("user_id") or payment.user_id,
                    user_email=payment.user_email,
                    payment_intent_id=payment_intent_id,
                    amount=payment.amount,
                    currency=payment.currency,
                    reason=cancellation_reason,
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
