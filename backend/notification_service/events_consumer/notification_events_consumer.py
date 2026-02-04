from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitQueue

from shared.shared_instances import logger, user_notification_email_service, order_notification_email_service
from shared.schemas.event_schemas import (
    UserRegisteredEvent,
    PasswordResetRequestedEvent,
    UserLoginEvent,
    PasswordResetSuccessEvent,
    OrderCreatedEvent,
    OrderConfirmedEvent,
    OrderCancelledEvent
)
from shared.shared_instances import broker


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
    "user.events",
    durable=True,
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": "user.events.dlq"
    }
)

order_events_queue = RabbitQueue(
    "order.events",
    durable=True,
    arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": "order.events.dlq"
    }
)


@broker.subscriber(queue=user_events_queue)
async def handle_user_events(message: dict[str, Any]):
    """Handle user registration and password reset events"""
    match message.get("event_type"):
        case "user.registered":
            event = UserRegisteredEvent(**message)
            await user_notification_email_service.send_verification_email(event)
        case "user.logged.in":
            event = UserLoginEvent(**message)
            await user_notification_email_service.send_login_notification_email(event)
        case "user.password.reset.request":
            event = PasswordResetRequestedEvent(**message)
            await user_notification_email_service.send_password_reset_email(event)
        case "user.password.reset.success":
            event = PasswordResetSuccessEvent(**message)
            await user_notification_email_service.send_password_reset_success_email(event)
        case _:
            logger.warning(f"Unhandled user event type: {message.get('event_type')}")


@broker.subscriber(queue=order_events_queue)
async def handle_order_events(message: dict[str, Any]):
    """Handle order-related notification events."""
    match message.get("event_type"):
        case "order.created":
            event = OrderCreatedEvent(**message)
            await order_notification_email_service.send_order_created_notification(event)
        case "order.confirmed":
            event = OrderConfirmedEvent(**message)
            await order_notification_email_service.send_order_confirmed_notification(event)
        case "order.cancelled":
            event = OrderCancelledEvent(**message)
            await order_notification_email_service.send_order_cancelled_notification(event)
        case _:
            logger.warning(f"Unhandled order event type: {message.get("event_type")}")
