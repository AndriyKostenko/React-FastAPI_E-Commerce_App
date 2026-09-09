from typing import Any

from resources import logger, settings
from shared.email_service.email_service import UserRelatedNotifications, OrderRelatedNotifications
from shared.contracts.events import (
    UserRegisteredEvent,
    EmailVerificationEvent,
    PasswordResetRequestedEvent,
    UserLoginEvent,
    PasswordResetSuccessEvent,
    OrderConfirmedEvent,
    OrderCancelledEvent,
    CJOrderShippedEvent,
    CJOrderDeliveredEvent,
    OrderDeliveredBaseEvent,
    OrderShippedBaseEvent,
    ProductionJobDeliveredEvent,
    ProductionJobShippedEvent,
)
from shared.enums.event_enums import ProductionEvents
from .broker import taskiq_broker


user_notification_email_service = UserRelatedNotifications(settings=settings, logger=logger)
order_notification_email_service = OrderRelatedNotifications(settings=settings, logger=logger)


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

def _parse_shipped_event(payload: dict[str, Any]) -> OrderShippedBaseEvent:
    """Read a dispatch notice from whichever channel actually posted it.

    A dropshipped parcel and a garment printed at home reach the customer
    through the same email, so the task accepts both event shapes and the
    template only ever sees the fields they share.
    """
    if payload.get("event_type") == ProductionEvents.PRODUCTION_JOB_SHIPPED:
        return ProductionJobShippedEvent(**payload)
    return CJOrderShippedEvent(**payload)


def _parse_delivered_event(payload: dict[str, Any]) -> OrderDeliveredBaseEvent:
    """Read a delivery confirmation from whichever channel reported it."""
    if payload.get("event_type") == ProductionEvents.PRODUCTION_JOB_DELIVERED:
        return ProductionJobDeliveredEvent(**payload)
    return CJOrderDeliveredEvent(**payload)


@taskiq_broker.task
async def send_order_shipped_email(payload: dict[str, Any]) -> None:
    event = _parse_shipped_event(payload)
    await order_notification_email_service.send_order_shipped_notification(event)
    logger.info(f"Order shipped email sent to {event.user_email} for order {event.order_id}")

@taskiq_broker.task
async def send_order_delivered_email(payload: dict[str, Any]) -> None:
    event = _parse_delivered_event(payload)
    await order_notification_email_service.send_order_delivered_notification(event)
    logger.info(f"Order delivered email sent to {event.user_email} for order {event.order_id}")
