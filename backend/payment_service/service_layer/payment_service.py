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
    PaymentCaptureError,
    PaymentDataIsNotProvided
)
from shared.contracts.events import (
    PaymentAuthorizedEvent,
    PaymentSucceededEvent,
    PaymentRefundedEvent,
    PaymentCancelledEvent,
)
from shared.enums.event_enums import PaymentEvents
from shared.enums.status_enums import PaymentStatus
from shared.enums.services_enums import Services
from schemas.payment_schemas import PaymentResponse
from shared.settings import Settings


class PaymentService:
    """Business logic layer for payment management using Stripe."""

    def __init__(self,
                repository: PaymentRepository,
                outbox_event_service: OutboxEventService,
                settings: Settings,
                logger: Logger,
                stripe_client: StripeClient | None = None) -> None:
        self.logger: Logger = logger
        self.settings: Settings = settings
        self.repository: PaymentRepository = repository
        self.outbox_event_service: OutboxEventService = outbox_event_service
        self.webhook_endpoint : str= self.settings.FULL_STRIPE_WEBHOOK_ENDPOINT
        self._webhook_secret: str = self.settings.STRIPE_WEBHOOK_SIGNING_SECRET
        self._stripe_api_key: str = self.settings.STRIPE_API_KEY
        self._stripe: StripeClient = stripe_client or StripeClient(
            api_key=self._stripe_api_key,
            max_network_retries=self.settings.STRIPE_MAX_NETWORK_RETRIES,
        )

    def _create_intent_idempotency_key(self, order_id: UUID) -> str:
        return f"payment_intent:create:{order_id}"

    def _refund_idempotency_key(self, order_id: UUID) -> str:
        return f"payment_refund:create:{order_id}"

    def _capture_idempotency_key(self, order_id: UUID) -> str:
        return f"payment_intent:capture:{order_id}"

    async def _create_refund(self, payment: Payment) -> Any:
        """Create at most one Stripe refund across retries and worker crashes."""
        return await self._stripe.v1.refunds.create_async(
            {"payment_intent": payment.stripe_payment_intent_id},
            options={"idempotency_key": self._refund_idempotency_key(payment.order_id)},
        )

    async def _create_stripe_payment_intent(
        self,
        order_id: UUID,
        user_id: UUID,
        user_email: str,
        amount: int,
        currency: str) -> Any:
        return await self._stripe.v1.payment_intents.create_async(
            {
                "amount": amount,
                "currency": currency,
                "metadata": {
                    "order_id": str(order_id),
                    "user_id": str(user_id),
                    "user_email": user_email,
                },
                "automatic_payment_methods": {"enabled": True},
                # Authorize only. The card is charged once the order's goods
                # are secured, so a failed fulfillment voids a hold instead of
                # refunding a charge (and losing Stripe's fee on it).
                "capture_method": "manual",
            },
            options={"idempotency_key": self._create_intent_idempotency_key(order_id)},
        )

    async def _finish_read_phase(self) -> None:
        """Release the connection before waiting on Stripe.

        SQLAlchemy autobegins a transaction on the first SELECT.  These payment
        workflows intentionally split into read -> remote I/O -> write phases,
        so the read-only phase must finish before the potentially slow network
        call.  ``expire_on_commit=False`` keeps the loaded snapshot usable; the
        Stripe idempotency keys make retrying an uncertain remote result safe.
        """
        await self.repository.session.commit()

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

            if existing_payment and existing_payment.status in {
                PaymentStatus.AUTHORIZED,
                PaymentStatus.SUCCEEDED,
                PaymentStatus.REFUNDED,
            }:
                raise PaymentAlreadyFinalizedError(order_id=order_id)

            if existing_payment and existing_payment.status == PaymentStatus.PENDING:
                await self._finish_read_phase()
                existing_intent = await self._stripe.v1.payment_intents.retrieve_async(
                    existing_payment.stripe_payment_intent_id
                )
                return {
                    "client_secret": existing_intent.client_secret,
                    "stripe_payment_intent_id": existing_payment.stripe_payment_intent_id,
                    "payment_id": str(existing_payment.id),
                    "order_id": str(order_id),
                    "amount": existing_payment.amount,
                    "currency": existing_payment.currency,
                }

            await self._finish_read_phase()
            intent = await self._create_stripe_payment_intent(
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
            "amount": amount,
            "currency": currency,
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

    async def handle_payment_intent_amount_capturable_updated(
        self, stripe_event_data: dict[str, Any]
    ) -> None:
        """
        Handle payment_intent.amount_capturable_updated: the card is authorized.

        The event carries Stripe's own authorized amount and currency rather
        than the stored ones, so order_service validates what the card actually
        holds against the canonical order.
        """
        intent = stripe_event_data["object"]
        payment_intent_id: str = intent["id"]

        payment = await self.repository.get_by_field(
            field_name="stripe_payment_intent_id", value=payment_intent_id
        )
        if not payment:
            raise PaymentNotFoundError(payment_id=payment_intent_id)
        if payment.status != PaymentStatus.PENDING:
            # Already authorized, captured, or released: a replay changes nothing.
            return

        async with self.repository.session.begin_nested():
            await self.repository.update_by_id(
                item_id=payment.id,
                data={"status": PaymentStatus.AUTHORIZED, "failure_reason": None},
            )
            await self.outbox_event_service.add_outbox_event(
                event_type=PaymentEvents.PAYMENT_AUTHORIZED,
                payload=PaymentAuthorizedEvent(
                    service=Services.PAYMENT_SERVICE,
                    event_type=PaymentEvents.PAYMENT_AUTHORIZED,
                    order_id=payment.order_id,
                    user_id=payment.user_id,
                    user_email=payment.user_email,
                    payment_intent_id=payment_intent_id,
                    amount=intent.get("amount_capturable") or payment.amount,
                    currency=intent.get("currency") or payment.currency,
                ),
            )

    async def capture_payment(self, order_id: UUID) -> Payment | None:
        """
        Charge the card authorized for ``order_id``.

        Safe to repeat: a captured payment is left alone, and the Stripe
        idempotency key makes a retried capture after an uncertain response
        return the original result. An authorization Stripe already voided or
        let expire is recorded as cancelled instead of being retried forever.
        """
        payment = await self.repository.get_by_field(field_name="order_id", value=order_id)
        if not payment:
            raise PaymentNotFoundError(payment_id=order_id)
        if payment.status == PaymentStatus.SUCCEEDED:
            return payment
        if payment.status != PaymentStatus.AUTHORIZED:
            self.logger.warning(
                f"Capture requested for order {order_id} but its payment is "
                f"{payment.status}; nothing to capture"
            )
            return payment

        # Lines refunded before capture are simply not charged.
        reduction_used = payment.capture_reduction_cents
        capture_params = (
            {"amount_to_capture": payment.amount - reduction_used} if reduction_used else None
        )
        await self._finish_read_phase()
        try:
            await self._stripe.v1.payment_intents.capture_async(
                payment.stripe_payment_intent_id,
                capture_params,
                options={"idempotency_key": self._capture_idempotency_key(order_id)},
            )
        except StripeError as exc:
            try:
                intent = await self._stripe.v1.payment_intents.retrieve_async(
                    payment.stripe_payment_intent_id
                )
            except StripeError as reconcile_exc:
                raise PaymentCaptureError(detail=str(reconcile_exc)) from reconcile_exc
            if intent.status == "canceled":
                self.logger.critical(
                    f"Authorization for order {order_id} was cancelled before capture "
                    f"({intent.cancellation_reason}); the order was not charged"
                )
                return await self._record_cancelled(
                    payment, reason="Authorization was cancelled before capture"
                )
            if intent.status != "succeeded":
                raise PaymentCaptureError(detail=str(exc)) from exc

        async with self.repository.session.begin_nested():
            locked = await self.repository.get_by_order_for_update(order_id)
            # A reduction recorded between reading the amount and Stripe
            # capturing was charged anyway: convert it into a refund, reserved
            # here under the lock and made on Stripe once this commits.
            late_cents = (locked.capture_reduction_cents - reduction_used) if locked else 0
            if locked is not None and late_cents > 0:
                locked.capture_reduction_cents = reduction_used
                locked.refunded_cents += late_cents
            updated = await self.repository.update_by_id(
                item_id=payment.id,
                data={"status": PaymentStatus.SUCCEEDED},
            )
            await self.outbox_event_service.add_outbox_event(
                event_type=PaymentEvents.PAYMENT_SUCCEEDED,
                payload=PaymentSucceededEvent(
                    service=Services.PAYMENT_SERVICE,
                    event_type=PaymentEvents.PAYMENT_SUCCEEDED,
                    order_id=payment.order_id,
                    user_id=payment.user_id,
                    user_email=payment.user_email,
                    payment_intent_id=payment.stripe_payment_intent_id,
                    amount=payment.amount,
                    currency=payment.currency,
                ),
            )
        if late_cents > 0:
            await self._refund_late_reduction(payment, late_cents)
        return updated

    async def _refund_late_reduction(self, payment: Payment, late_cents: int) -> None:
        await self._finish_read_phase()  # the reservation is committed first
        try:
            await self._stripe.v1.refunds.create_async(
                {"payment_intent": payment.stripe_payment_intent_id, "amount": late_cents},
                options={"idempotency_key": f"payment_refund:late_reduction:{payment.order_id}"},
            )
        except StripeError as exc:
            self.logger.critical(
                "RECONCILIATION REQUIRED for order %s: %s cents reduced before capture "
                "were charged and could not be refunded: %s",
                payment.order_id, late_cents, exc,
            )

    async def _record_cancelled(self, payment: Payment, reason: str) -> Payment | None:
        async with self.repository.session.begin_nested():
            updated = await self.repository.update_by_id(
                item_id=payment.id,
                data={"status": PaymentStatus.CANCELLED, "failure_reason": reason},
            )
            await self.outbox_event_service.add_outbox_event(
                event_type=PaymentEvents.PAYMENT_CANCELLED,
                payload=PaymentCancelledEvent(
                    service=Services.PAYMENT_SERVICE,
                    event_type=PaymentEvents.PAYMENT_CANCELLED,
                    order_id=payment.order_id,
                    user_id=payment.user_id,
                    user_email=payment.user_email,
                    payment_intent_id=payment.stripe_payment_intent_id,
                    amount=payment.amount,
                    currency=payment.currency,
                    reason=reason,
                ),
            )
        return updated

    async def handle_payment_intent_succeeded(self, stripe_event_data: dict[str, Any]) -> None:
        """
        Handle payment_intent.succeeded webhook event: the charge is captured.

        ``capture_payment`` normally records this first, so the webhook only
        acts for a capture made elsewhere (e.g. from the Stripe dashboard).
        """
        intent = stripe_event_data["object"]
        payment_intent_id: str = intent["id"]
        metadata: dict[str, Any] = intent.get("metadata", {})

        payment = await self.repository.get_by_field(
            field_name="stripe_payment_intent_id", value=payment_intent_id
        )
        if not payment:
            raise PaymentNotFoundError(payment_id=payment_intent_id)
        if payment.status in {PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED}:
            return

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
        Handle payment_intent.payment_failed: one attempt was declined.

        A decline is not terminal. The PaymentIntent stays open and the
        customer can retry with another card, so only the reason is recorded;
        the order is released by a cancelled intent or the Saga timeout.
        """
        intent = stripe_event_data["object"]
        payment_intent_id: str = intent["id"]
        failure_reason: str = (
            intent.get("last_payment_error", {}) or {}
        ).get("message", "Unknown error")

        payment = await self.repository.get_by_field(
            field_name="stripe_payment_intent_id", value=payment_intent_id
        )
        if not payment:
            raise PaymentNotFoundError(payment_id=payment_intent_id)
        if payment.status != PaymentStatus.PENDING:
            return

        async with self.repository.session.begin_nested():
            await self.repository.update_by_id(
                item_id=payment.id,
                data={"failure_reason": failure_reason},
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

        if payment.status in {PaymentStatus.PENDING, PaymentStatus.AUTHORIZED}:
            # Nothing has been charged yet: cancelling the intent voids any hold.
            await self._finish_read_phase()
            try:
                await self._stripe.v1.payment_intents.cancel_async(
                    payment.stripe_payment_intent_id
                )
            except StripeError as exc:
                # A success webhook may race cancellation. If Stripe says the
                # intent succeeded, refund it instead of leaving a charge behind.
                try:
                    intent = await self._stripe.v1.payment_intents.retrieve_async(
                        payment.stripe_payment_intent_id
                    )
                    if intent.status == "canceled":
                        new_status = PaymentStatus.CANCELLED
                    elif intent.status != "succeeded":
                        raise PaymentRefundError(detail=str(exc))
                    else:
                        await self._create_refund(payment)
                        new_status = PaymentStatus.REFUNDED
                except StripeError as reconcile_exc:
                    raise PaymentRefundError(detail=str(reconcile_exc)) from reconcile_exc
            else:
                new_status = PaymentStatus.CANCELLED

            async with self.repository.session.begin_nested():
                updated = await self.repository.update_by_id(
                    item_id=payment.id,
                    data={"status": new_status},
                )
                if new_status == PaymentStatus.CANCELLED:
                    await self.outbox_event_service.add_outbox_event(
                        event_type=PaymentEvents.PAYMENT_CANCELLED,
                        payload=PaymentCancelledEvent(
                            service=Services.PAYMENT_SERVICE,
                            event_type=PaymentEvents.PAYMENT_CANCELLED,
                            order_id=payment.order_id,
                            user_id=payment.user_id,
                            user_email=payment.user_email,
                            payment_intent_id=payment.stripe_payment_intent_id,
                            amount=payment.amount,
                            currency=payment.currency,
                            reason="Order cancelled before payment was captured",
                        ),
                    )
                else:
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
            return updated

        if payment.status != PaymentStatus.SUCCEEDED:
            # Nothing to refund — payment was never charged or already refunded/failed
            return payment

        await self._finish_read_phase()
        try:
            _ = await self._create_refund(payment)
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
        if payment.status in {PaymentStatus.CANCELLED, PaymentStatus.REFUNDED}:
            # Our own void already recorded this, from order cancellation.
            return

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

    async def get_payments(self) -> list[PaymentResponse]:
        payments = await self.repository.get_all()
        return [PaymentResponse.model_validate(payment) for payment in payments]
