from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitQueue
from orjson import loads

from shared.shared_instances import logger, user_notification_email_service, order_notification_email_service
from shared.schemas.event_schemas import (
    EmailVerificationEvent,
    UserRegisteredEvent,
    PasswordResetRequestedEvent,
    UserLoginEvent,
    PasswordResetSuccessEvent,
    OrderConfirmedEvent,
    OrderCancelledEvent
)
from shared.shared_instances import broker
from shared.enums.event_enums import UserEvents, OrderEvents, UserEventsQueue, OrderEventsQueue


"""
The FastStream app (app) will be executed by faststream run via the command line,
so no manual uvicorn setup is needed.
Don't need to specify host or port, as faststream run doesn't serve HTTP endpoints—it
connects directly to RabbitMQ
"""


# Create the FastStream app
app = FastStream(broker)


# Define queues and their dead-letter settings
user_events_queue = RabbitQueue(
    UserEventsQueue.USER_EVENTS_QUEUE,
    durable=True,
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": UserEventsQueue.USER_EVENTS_DEAD_LETTER_QUEUE
    }
)

order_events_queue = RabbitQueue(
    OrderEventsQueue.ORDER_EVENTS_QUEUE,
    durable=True,
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": OrderEventsQueue.ORDER_EVENTS_DEAD_LETTER_QUEUE
    }
)


@broker.subscriber(queue=user_events_queue)
async def handle_user_events(body: str):
    """Handle user-related events"""
    message: dict[str, Any] = loads(body)
    event_type = message.get("event_type")
    match event_type:
        case UserEvents.USER_REGISTERED:
            event = UserRegisteredEvent(**message)
            await user_notification_email_service.send_verification_email(event)
        case UserEvents.USER_EMAIL_VERIFIED:
            event = EmailVerificationEvent(**message)
            await user_notification_email_service.send_email_verified_notification(event)
        case UserEvents.USER_LOGGED_IN:
            event = UserLoginEvent(**message)
            await user_notification_email_service.send_login_notification_email(event)
        case UserEvents.USER_PASSWORD_RESET_REQUEST:
            event = PasswordResetRequestedEvent(**message)
            await user_notification_email_service.send_password_reset_email(event)
        case UserEvents.USER_PASSWORD_RESET_SUCCESS:
            event = PasswordResetSuccessEvent(**message)
            await user_notification_email_service.send_password_reset_success_email(event)
        case _:
            logger.warning(f"Unhandled user event type: {message.get('event_type')}")


@broker.subscriber(queue=order_events_queue)
async def handle_order_events(body: str):
    """Handle order-related notification events."""
    message: dict[str, Any] = loads(body)
    event_type = message.get("event_type")
    match event_type:
        case OrderEvents.ORDER_CONFIRMED:
            event = OrderConfirmedEvent(**message)
            await order_notification_email_service.send_order_confirmed_notification(event)
        case OrderEvents.ORDER_CANCELLED:
            event = OrderCancelledEvent(**message)
            await order_notification_email_service.send_order_cancelled_notification(event)
        case _:
            logger.warning(f"Unhandled order event type: {message.get("event_type")}")
