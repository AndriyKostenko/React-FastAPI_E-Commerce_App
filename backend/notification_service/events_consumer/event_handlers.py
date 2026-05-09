from logging import Logger
from typing import Any
from uuid import UUID

from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.shared_instances import (
    logger,
    notification_idempotency_service,
    notification_service_database_session_manager,
    user_notification_email_service,
    order_notification_email_service,
)
from shared.schemas.event_schemas import (
    EmailVerificationEvent,
    UserRegisteredEvent,
    PasswordResetRequestedEvent,
    UserLoginEvent,
    PasswordResetSuccessEvent,
    OrderConfirmedEvent,
    OrderCancelledEvent,
    PaymentSucceededEvent,
    PaymentFailedEvent,
    PaymentRefundedEvent,
    PaymentCancelledEvent,
)
from shared.enums.event_enums import UserEvents, OrderEvents, PaymentEvents
from service_layer.notification_service import NotificationService
from database_layer.notification_repository import NotificationRepository
from tasks.email_tasks import (
    send_verification_email,
    send_email_verified_notification,
    send_login_notification,
    send_password_reset_email,
    send_password_reset_success,
)

"""
Base handler
Composition over inheritance: handlers USE IdempotencyEventService and
DatabaseSessionManager - they don't specialize them.
Both handlers share the single notification_idempotency_service singleton
(one Redis connection pool for the whole notification consumer process).
"""

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


# User event handler

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

            match event_type:
                case UserEvents.USER_REGISTERED:
                    await send_verification_email.kiq(message)       # sending to TaskiQ queue .kiq() instead of direct call
                    notification_message = "Welcome! Please verify your email address."
                case UserEvents.USER_EMAIL_VERIFIED:
                    await send_email_verified_notification.kiq(message)
                    notification_message = "Your email address has been successfully verified."
                case UserEvents.USER_LOGGED_IN:
                    await send_login_notification.kiq(message)
                    notification_message = "A new login was detected on your account."
                case UserEvents.USER_PASSWORD_RESET_REQUEST:
                    await send_password_reset_email.kiq(message)
                    notification_message = "A password reset has been requested."
                case UserEvents.USER_PASSWORD_RESET_SUCCESS:
                    await send_password_reset_success.kiq(message)
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
            await self._mark_processed(event_id=event_id, event_type=event_type)

        except Exception as error:
            self._logger.error(f"Error handling user event {event_type}: {error}")
            await self._release_claim(event_id=event_id, event_type=event_type)
            raise


# Order event handler

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

            match event_type:
                case OrderEvents.ORDER_CREATED:
                    self._logger.info(f"Order created event received for order: {order_id}, skipping notification.")
                    await self._mark_processed(event_id=event_id, event_type=event_type, order_id=order_id, result="skipped")
                    return
                case OrderEvents.ORDER_CONFIRMED:
                    event = OrderConfirmedEvent(**message)
                    await order_notification_email_service.send_order_confirmed_notification(event)
                    notification_message = f"Your order #{order_id} has been confirmed."
                case OrderEvents.ORDER_CANCELLED:
                    event = OrderCancelledEvent(**message)
                    await order_notification_email_service.send_order_cancelled_notification(event)
                    notification_message = f"Your order #{order_id} has been cancelled."
                case _:
                    self._logger.warning(f"Unhandled order event type: {event_type}")
                    await self._mark_processed(event_id=event_id, event_type=event_type, order_id=order_id, result="skipped")
                    return

            await self._save_notification(user_id=user_id,message=notification_message,notification_type=event_type)
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
            await self._mark_processed(event_id=event_id, event_type=event_type, order_id=order_id)

        except Exception as error:
            self._logger.error(f"Error handling payment event {event_type}: {error}")
            await self._release_claim(event_id=event_id, event_type=event_type)
            raise


# FastStream subscriber registration
# Both handlers share the SAME notification_idempotency_service singleton -
# one Redis connection pool for the entire notification consumer process.

user_handler = UserEventHandler(
    idempotency_service=notification_idempotency_service,
    db_session_manager=notification_service_database_session_manager,
    logger=logger,
)
order_handler = OrderEventHandler(
    idempotency_service=notification_idempotency_service,
    db_session_manager=notification_service_database_session_manager,
    logger=logger,
)
payment_handler = PaymentEventHandler(
    idempotency_service=notification_idempotency_service,
    db_session_manager=notification_service_database_session_manager,
    logger=logger,
)
