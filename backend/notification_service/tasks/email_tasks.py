from typing import Any

from shared.shared_instances import (
    user_notification_email_service,
    order_notification_email_service,
    logger,
    taskiq_broker
)
from shared.schemas.event_schemas import (
    UserRegisteredEvent,
    EmailVerificationEvent,
    PasswordResetRequestedEvent,
    UserLoginEvent,
    PasswordResetSuccessEvent,
    OrderConfirmedEvent,
    OrderCancelledEvent,
)


@taskiq_broker.task
async def send_verification_email(payload: dict[str, Any]) -> None:
    event = UserRegisteredEvent(**payload)
    await user_notification_email_service.send_verification_email(event)
    logger.info(f"Verification email sent to {event.user_email}")

@taskiq_broker.task
async def send_email_verified_notification(payload: dict[str, Any]) -> None:
    event = EmailVerificationEvent(**payload)
    await user_notification_email_service.send_email_verified_notification(event)
    logger.info(f"Email verified notification sent to {event.user_email}")

@taskiq_broker.task
async def send_login_notification(payload: dict[str, Any]) -> None:
    event = UserLoginEvent(**payload)
    await user_notification_email_service.send_login_notification_email(event)
    logger.info(f"Login notification email sent to {event.user_email}")

@taskiq_broker.task
async def send_password_reset_email(payload: dict[str, Any]) -> None:
    event = PasswordResetRequestedEvent(**payload)
    await user_notification_email_service.send_password_reset_email(event)
    logger.info(f"Password reset email sent to {event.user_email}")

@taskiq_broker.task
async def send_password_reset_success(payload: dict[str, Any]) -> None:
    event = PasswordResetSuccessEvent(**payload)
    await user_notification_email_service.send_password_reset_success_email(event)
    logger.info(f"Password reset success email sent to {event.user_email}")

@taskiq_broker.task
async def send_order_confirmed_email(payload: dict[str, Any]) -> None:
    event = OrderConfirmedEvent(**payload)
    await order_notification_email_service.send_order_confirmed_notification(event)
    logger.info(f"Order confirmed email sent to {event.user_email} for order {event.order_id}")

@taskiq_broker.task
async def send_order_cancelled_email(payload: dict[str, Any]) -> None:
    event = OrderCancelledEvent(**payload)
    await order_notification_email_service.send_order_cancelled_notification(event)
    logger.info(f"Order cancelled email sent to {event.user_email} for order {event.order_id}")
