from typing import Any
from uuid import UUID

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
from shared.shared_instances import broker, notification_idempotency_service
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
    """Handle user-related events with idempotency checking."""
    message: dict[str, Any] = loads(body)
    event_type: str = message["event_type"]
    event_id: UUID = message["event_id"]

    # Atomically claim the event — skip if already claimed/processed
    if event_id and not await notification_idempotency_service.try_claim_event(
        event_id=event_id, event_type=event_type
    ):
        logger.debug(f"Skipping duplicate user event: {event_type} / {event_id}")
        return

    try:
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
                return

        # Mark as processed AFTER successful handling
        if event_id:
            await notification_idempotency_service.mark_event_as_processed(
                event_id=event_id,
                event_type=event_type,
                order_id=None,
                result="sent"
            )
    except Exception as error:
        logger.error(f"Error handling user event {event_type}: {error}")
        raise


@broker.subscriber(queue=order_events_queue)
async def handle_order_events(body: str):
    """Handle order-related notification events with idempotency checking."""
    message: dict[str, Any] = loads(body)
    event_type: str = message["event_type"]
    event_id: UUID = message["event_id"]

    # Atomically claim the event — skip if already claimed/processed
    if event_id and not await notification_idempotency_service.try_claim_event(
        event_id=event_id, event_type=event_type
    ):
        logger.debug(f"Skipping duplicate order event: {event_type} / {event_id}")
        return

    try:
        match event_type:
            case OrderEvents.ORDER_CREATED:
                logger.info(f"Order created event received for order: {message.get('order_id')}, skipping notification.")
            case OrderEvents.ORDER_CONFIRMED:
                event = OrderConfirmedEvent(**message)
                await order_notification_email_service.send_order_confirmed_notification(event)
            case OrderEvents.ORDER_CANCELLED:
                event = OrderCancelledEvent(**message)
                await order_notification_email_service.send_order_cancelled_notification(event)
            case _:
                logger.warning(f"Unhandled order event type: {message.get('event_type')}")
                return

        # Mark as processed AFTER successful handling (covers all matched cases)
        if event_id:
            order_id = message.get("order_id")
            await notification_idempotency_service.mark_event_as_processed(
                event_id=event_id,
                event_type=event_type,
                order_id=order_id,
                result="sent"
            )
    except Exception as error:
        logger.error(f"Error handling order event {event_type}: {error}")
        raise
