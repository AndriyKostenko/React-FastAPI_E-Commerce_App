from logging import Logger
from typing import Any
from uuid import UUID

from orjson import loads

from shared.idempotency_service import IdempotencyEventService
from shared.database_setup import DatabaseSessionManager
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
)
from shared.enums.event_enums import UserEvents, OrderEvents
from service_layer.notification_service import NotificationService
from database_layer.notification_repository import NotificationRepository

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

    async def _mark_processed(self, event_id: str, event_type: str, order_id: str | None = None) -> None:
        await self._idempotency.mark_event_as_processed(
            event_id=event_id,
            event_type=event_type,
            order_id=order_id,
            result="sent",
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

    async def handle(self, body: str) -> None:
        """Handle user-related events with idempotency checking."""
        message: dict[str, Any] = loads(body)
        event_type: str = message["event_type"]
        event_id: str = message["event_id"]

        if event_id and not await self._try_claim(event_id, event_type):
            self._logger.debug(f"Skipping duplicate user event: {event_type} / {event_id}")
            return

        try:
            user_id = self._parse_user_id(message)
            notification_message: str

            match event_type:
                case UserEvents.USER_REGISTERED:
                    event = UserRegisteredEvent(**message)
                    await user_notification_email_service.send_verification_email(event)
                    notification_message = "Welcome! Please verify your email address to activate your account."
                case UserEvents.USER_EMAIL_VERIFIED:
                    event = EmailVerificationEvent(**message)
                    await user_notification_email_service.send_email_verified_notification(event)
                    notification_message = "Your email address has been successfully verified."
                case UserEvents.USER_LOGGED_IN:
                    event = UserLoginEvent(**message)
                    await user_notification_email_service.send_login_notification_email(event)
                    notification_message = "A new login was detected on your account."
                case UserEvents.USER_PASSWORD_RESET_REQUEST:
                    event = PasswordResetRequestedEvent(**message)
                    await user_notification_email_service.send_password_reset_email(event)
                    notification_message = "A password reset has been requested for your account."
                case UserEvents.USER_PASSWORD_RESET_SUCCESS:
                    event = PasswordResetSuccessEvent(**message)
                    await user_notification_email_service.send_password_reset_success_email(event)
                    notification_message = "Your password has been reset successfully."
                case _:
                    self._logger.warning(f"Unhandled user event type: {event_type}")
                    return

            await self._save_notification(
                user_id=user_id,
                message=notification_message,
                notification_type=event_type,
            )
            if event_id:
                await self._mark_processed(event_id=event_id, event_type=event_type)

        except Exception as error:
            self._logger.error(f"Error handling user event {event_type}: {error}")
            raise


# Order event handler

class OrderEventHandler(BaseEventHandler):

    async def handle(self, body: str) -> None:
        """Handle order-related notification events with idempotency checking."""
        message: dict[str, Any] = loads(body)
        event_type: str = message["event_type"]
        event_id: str = message["event_id"]

        if event_id and not await self._try_claim(event_id, event_type):
            self._logger.debug(f"Skipping duplicate order event: {event_type} / {event_id}")
            return

        try:
            user_id = self._parse_user_id(message)
            order_id: str | None = message.get("order_id")
            notification_message: str

            match event_type:
                case OrderEvents.ORDER_CREATED:
                    self._logger.info(f"Order created event received for order: {order_id}, skipping notification.")
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
                    return

            await self._save_notification(user_id=user_id,message=notification_message,notification_type=event_type)
            if event_id:
                await self._mark_processed(event_id=event_id, event_type=event_type, order_id=order_id)

        except Exception as error:
            self._logger.error(f"Error handling order event {event_type}: {error}")
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
