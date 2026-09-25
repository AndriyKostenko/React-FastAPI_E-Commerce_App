from logging import Logger
from typing import Any
from uuid import UUID

from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.managers.database_session_manager import DatabaseSessionManager
from taskiq import AsyncTaskiqDecoratedTask
from shared.contracts.events import (
    CJOrderDeliveredEvent,
    CJOrderShippedEvent,
    ProductionJobCancelledEvent,
    ProductionJobDeliveredEvent,
    ProductionJobShippedEvent,
    PaymentSucceededEvent,
    PaymentFailedEvent,
    PaymentRefundedEvent,
    PaymentCancelledEvent,
)
from shared.enums.event_enums import (
    OrderEvents,
    PaymentEvents,
    ProductionEvents,
    UserEvents,
)
from service_layer.notification_service import NotificationService
from database_layer.notification_repository import NotificationRepository
from tasks.email_tasks import (
    send_verification_email,
    send_email_verified_notification,
    send_login_notification,
    send_password_reset_email,
    send_password_reset_success,
    send_order_confirmed_email,
    send_order_cancelled_email,
    send_order_shipped_email,
    send_order_delivered_email,
)

"""
Base handler
Composition over inheritance: handlers USE IdempotencyEventService and
DatabaseSessionManager - they don't specialize them.
All handlers receive the same consumer-owned idempotency resource
(one Redis connection pool for the whole notification consumer process).
"""

# An email task, chosen by the event and enqueued after the notification is saved.
type EmailTask = AsyncTaskiqDecoratedTask[[dict[str, Any]], None]


class BaseEventHandler:
    """
    Holds the two shared infrastructure dependencies - idempotency and DB - and
    exposes three convenience coroutines used by both concrete handlers.
    """

    def __init__(self,
                idempotency_service: IdempotencyEventService,
                db_session_manager: DatabaseSessionManager,
                logger: Logger) -> None:
        self._idempotency: IdempotencyEventService = idempotency_service
        self._db: DatabaseSessionManager = db_session_manager
        self._logger: Logger = logger

    async def _try_claim(self, event_id: str, event_type: str) -> bool:
        """Return True if this worker claimed the event, False if already taken."""
        return await self._idempotency.try_claim_event(event_id=event_id, event_type=event_type)

    async def _release_claim(self, event_id: str, event_type: str) -> None:
        """Delete the 'processing' marker so the event can be retried after a failure."""
        await self._idempotency.release_claim(event_id=event_id, event_type=event_type)

    async def _mark_processed(self, event_id: str, event_type: str, order_id: str | None = None, result: str = "sent") -> None:
        await self._idempotency.mark_event_as_processed(
            event_id=event_id,
            event_type=event_type,
            order_id=order_id,
            result=result,
        )

    async def _save_notification(self, user_id: UUID | None, message: str, notification_type: str) -> None:
        """Persist a notification record inside its own transaction."""
        async with self._db.transaction() as session:
            service = NotificationService(repository=NotificationRepository(session=session))
            await service.save_notification(message=message,notification_type=notification_type,user_id=user_id)

    @staticmethod
    def _parse_user_id(message: dict[str, Any]) -> UUID | None:
        raw = message.get("user_id")
        return UUID(raw) if raw else None


class UserEventHandler(BaseEventHandler):

    async def handle(self, body: dict[str, Any]) -> None:
        """Handle user-related events with idempotency checking."""
        message: dict[str, Any] = body
        event_type: str = message["event_type"]
        event_id: str = message["event_id"]

        # Idempotency check first - before any processing
        if not await self._try_claim(event_id, event_type):
            self._logger.debug(f"Skipping duplicate user event: {event_type} / {event_id}")
            return

        try:
            user_id = self._parse_user_id(message)
            notification_message: str

            email_task: EmailTask | None = None

            match event_type:
                case UserEvents.USER_REGISTERED:
                    email_task = send_verification_email
                    notification_message = "Welcome! Please verify your email address."
                case UserEvents.USER_EMAIL_VERIFIED:
                    email_task = send_email_verified_notification
                    notification_message = "Your email address has been successfully verified."
                case UserEvents.USER_LOGGED_IN:
                    email_task = send_login_notification
                    notification_message = "A new login was detected on your account."
                case UserEvents.USER_PASSWORD_RESET_REQUEST:
                    email_task = send_password_reset_email
                    notification_message = "A password reset has been requested."
                case UserEvents.USER_PASSWORD_RESET_SUCCESS:
                    email_task = send_password_reset_success
                    notification_message = "Your password has been reset successfully."
                case _:
                    self._logger.warning(f"Unhandled user event type: {event_type}")
                    return

            # DB save + idempotency mark stay here
            await self._save_notification(
                user_id=user_id,
                message=notification_message,
                notification_type=event_type,
            )
            # Enqueued only once the notification is committed: a failed save used to
            # release the claim after the email was already queued, so the retry sent it twice.
            if email_task is not None:
                await email_task.kiq(message)
            await self._mark_processed(event_id=event_id, event_type=event_type)

        except Exception as error:
            self._logger.error(f"Error handling user event {event_type}: {error}")
            await self._release_claim(event_id=event_id, event_type=event_type)
            raise


class OrderEventHandler(BaseEventHandler):

    async def handle(self, body: dict[str, Any]) -> None:
        """Handle order-related notification events with idempotency checking."""
        message: dict[str, Any] = body
        event_type: str = message["event_type"]
        event_id: str = message["event_id"]

        # Idempotency check first - before any processing
        if not await self._try_claim(event_id, event_type):
            self._logger.debug(f"Skipping duplicate order event: {event_type} / {event_id}")
            return

        try:
            user_id = self._parse_user_id(message)
            order_id: str | None = message.get("order_id")
            notification_message: str

            email_task: EmailTask | None = None

            match event_type:
                case OrderEvents.ORDER_CREATED:
                    self._logger.info(f"Order created event received for order: {order_id}, skipping notification.")
                    await self._mark_processed(event_id=event_id, event_type=event_type, order_id=order_id, result="skipped")
                    return
                case OrderEvents.ORDER_CONFIRMED:
                    email_task = send_order_confirmed_email
                    notification_message = f"Your order #{order_id} has been confirmed."
                case OrderEvents.ORDER_CANCELLED:
                    email_task = send_order_cancelled_email
                    notification_message = f"Your order #{order_id} has been cancelled."
                case _:
                    self._logger.warning(f"Unhandled order event type: {event_type}")
                    await self._mark_processed(event_id=event_id, event_type=event_type, order_id=order_id, result="skipped")
                    return

            await self._save_notification(user_id=user_id,message=notification_message,notification_type=event_type)

            # Enqueued only once the notification is committed: a failed save used to

            # release the claim after the email was already queued, so the retry sent it twice.

            if email_task is not None:

                await email_task.kiq(message)
            await self._mark_processed(event_id=event_id, event_type=event_type, order_id=order_id)

        except Exception as error:
            self._logger.error(f"Error handling order event {event_type}: {error}")
            await self._release_claim(event_id=event_id, event_type=event_type)
            raise


class PaymentEventHandler(BaseEventHandler):

    async def handle(self, body: dict[str, Any]) -> None:
        """Handle payment-related notification events with idempotency checking."""
        message: dict[str, Any] = body
        event_type: str = message["event_type"]
        event_id: str = message["event_id"]

        if not await self._try_claim(event_id, event_type):
            self._logger.debug(f"Skipping duplicate payment event: {event_type} / {event_id}")
            return

        try:
            user_id = self._parse_user_id(message)
            order_id: str | None = message.get("order_id")
            notification_message: str

            email_task: EmailTask | None = None

            match event_type:
                case PaymentEvents.PAYMENT_SUCCEEDED:
                    _ = PaymentSucceededEvent(**message)
                    notification_message = f"Payment for order #{order_id} succeeded."
                case PaymentEvents.PAYMENT_FAILED:
                    event = PaymentFailedEvent(**message)
                    notification_message = f"Payment for order #{order_id} failed: {event.reason}"
                case PaymentEvents.PAYMENT_REFUNDED:
                    _ = PaymentRefundedEvent(**message)
                    notification_message = f"Payment for order #{order_id} was refunded."
                case PaymentEvents.PAYMENT_CANCELLED:
                    event = PaymentCancelledEvent(**message)
                    notification_message = f"Payment for order #{order_id} was cancelled: {event.reason}"
                case _:
                    self._logger.warning(f"Unhandled payment event type: {event_type}")
                    await self._mark_processed(event_id=event_id, event_type=event_type, order_id=order_id, result="skipped")
                    return

            await self._save_notification(user_id=user_id, message=notification_message, notification_type=event_type)

            # Enqueued only once the notification is committed: a failed save used to

            # release the claim after the email was already queued, so the retry sent it twice.

            if email_task is not None:

                await email_task.kiq(message)
            await self._mark_processed(event_id=event_id, event_type=event_type, order_id=order_id)

        except Exception as error:
            self._logger.error(f"Error handling payment event {event_type}: {error}")
            await self._release_claim(event_id=event_id, event_type=event_type)
            raise


class CJOrderEventHandler(BaseEventHandler):
    """Notifies the customer about CJ-fulfilled shipping progress.

    These events use the "cj.order.*" routing key, which the "order.#" binding
    of OrderEventHandler deliberately does not match, so they arrive on their
    own queue and are handled here.
    """

    async def handle(self, body: dict[str, Any]) -> None:
        """Handle CJ fulfillment events with idempotency checking."""
        message: dict[str, Any] = body
        event_type: str = message["event_type"]
        event_id: str = message["event_id"]

        if not await self._try_claim(event_id, event_type):
            self._logger.debug(f"Skipping duplicate CJ order event: {event_type} / {event_id}")
            return

        try:
            user_id = self._parse_user_id(message)
            order_id: str | None = message.get("order_id")
            notification_message: str

            email_task: EmailTask | None = None

            match event_type:
                case OrderEvents.CJ_ORDER_SHIPPED:
                    event = CJOrderShippedEvent(**message)
                    email_task = send_order_shipped_email
                    notification_message = (
                        f"Your order #{order_id} has shipped. "
                        f"Tracking number: {event.tracking_number}."
                    )
                case OrderEvents.CJ_ORDER_DELIVERED:
                    _ = CJOrderDeliveredEvent(**message)
                    email_task = send_order_delivered_email
                    notification_message = f"Your order #{order_id} has been delivered."
                case OrderEvents.CJ_ORDER_CREATED | OrderEvents.CJ_ORDER_FAILED:
                    # Fulfillment bookkeeping. The customer hears about a
                    # failure through order.cancelled, not from this queue.
                    self._logger.info(
                        f"CJ event {event_type} for order {order_id} needs no customer notification."
                    )
                    await self._mark_processed(
                        event_id=event_id, event_type=event_type, order_id=order_id, result="skipped"
                    )
                    return
                case _:
                    self._logger.warning(f"Unhandled CJ order event type: {event_type}")
                    await self._mark_processed(
                        event_id=event_id, event_type=event_type, order_id=order_id, result="skipped"
                    )
                    return

            await self._save_notification(
                user_id=user_id,
                message=notification_message,
                notification_type=event_type,
            )

            # Enqueued only once the notification is committed: a failed save used to

            # release the claim after the email was already queued, so the retry sent it twice.

            if email_task is not None:

                await email_task.kiq(message)
            await self._mark_processed(event_id=event_id, event_type=event_type, order_id=order_id)

        except Exception as error:
            self._logger.error(f"Error handling CJ order event {event_type}: {error}")
            await self._release_claim(event_id=event_id, event_type=event_type)
            raise


class ProductionEventHandler(BaseEventHandler):
    """Tells the customer how their in-house printed garment is progressing.

    Custom T-shirts are printed and posted by hand rather than by a carrier
    integration, so this queue is the only thing that ever tells the buyer
    their order left the workshop. These events use the "production.job.*"
    routing key, which the "order.#" binding of OrderEventHandler deliberately
    does not match, so they arrive on their own queue and are handled here.
    """

    async def handle(self, body: dict[str, Any]) -> None:
        """Handle in-house production events with idempotency checking."""
        message: dict[str, Any] = body
        event_type: str = message["event_type"]
        event_id: str = message["event_id"]

        if not await self._try_claim(event_id, event_type):
            self._logger.debug(f"Skipping duplicate production event: {event_type} / {event_id}")
            return

        try:
            user_id = self._parse_user_id(message)
            order_id: str | None = message.get("order_id")
            notification_message: str

            email_task: EmailTask | None = None

            match event_type:
                case ProductionEvents.PRODUCTION_JOB_STARTED:
                    notification_message = (
                        f"Your custom item for order #{order_id} is now being printed."
                    )
                case ProductionEvents.PRODUCTION_JOB_PRINTED:
                    notification_message = (
                        f"Your custom item for order #{order_id} has been printed "
                        "and is being packed."
                    )
                case ProductionEvents.PRODUCTION_JOB_SHIPPED:
                    event = ProductionJobShippedEvent(**message)
                    email_task = send_order_shipped_email
                    notification_message = (
                        f"Your order #{order_id} has shipped. "
                        f"Tracking number: {event.tracking_number}."
                    )
                case ProductionEvents.PRODUCTION_JOB_DELIVERED:
                    _ = ProductionJobDeliveredEvent(**message)
                    email_task = send_order_delivered_email
                    notification_message = f"Your order #{order_id} has been delivered."
                case ProductionEvents.PRODUCTION_JOB_CANCELLED:
                    # Workshop bookkeeping. The customer hears about a
                    # cancellation through order.cancelled, not from this queue.
                    event = ProductionJobCancelledEvent(**message)
                    if event.reconciliation_required:
                        self._logger.critical(
                            f"Production job {event.job_id} for order {order_id} was "
                            f"cancelled after the garment was already made or posted "
                            f"({event.reason}) — a return decision is required."
                        )
                    await self._mark_processed(
                        event_id=event_id, event_type=event_type, order_id=order_id, result="skipped"
                    )
                    return
                case _:
                    self._logger.warning(f"Unhandled production event type: {event_type}")
                    await self._mark_processed(
                        event_id=event_id, event_type=event_type, order_id=order_id, result="skipped"
                    )
                    return

            await self._save_notification(
                user_id=user_id,
                message=notification_message,
                notification_type=event_type,
            )

            # Enqueued only once the notification is committed: a failed save used to

            # release the claim after the email was already queued, so the retry sent it twice.

            if email_task is not None:

                await email_task.kiq(message)
            await self._mark_processed(event_id=event_id, event_type=event_type, order_id=order_id)

        except Exception as error:
            self._logger.error(f"Error handling production event {event_type}: {error}")
            await self._release_claim(event_id=event_id, event_type=event_type)
            raise
