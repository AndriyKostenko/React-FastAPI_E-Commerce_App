from typing import Any

from shared.outbox import OutboxRelay
from shared.enums.event_enums import PaymentEvents
from events_publisher.payment_event_publisher import PaymentEventPublisher
from models.outbox_models import OutboxEvent
from resources import PaymentOutboxResources


async def route_payment_event(
    event_type: str,
    payload: dict[str, Any],
    publisher: PaymentEventPublisher,
) -> None:
    routes = {
        PaymentEvents.PAYMENT_SUCCEEDED: publisher.publish_payment_succeeded,
        PaymentEvents.PAYMENT_FAILED: publisher.publish_payment_failed,
        PaymentEvents.PAYMENT_REFUNDED: publisher.publish_payment_refunded,
        PaymentEvents.PAYMENT_CANCELLED: publisher.publish_payment_cancelled,
    }
    publish = routes.get(event_type)
    if not publish:
        raise ValueError(f"Unsupported payment outbox event type: {event_type}")
    await publish(payload)


def build_outbox_relay(resources: PaymentOutboxResources) -> OutboxRelay:
    async def event_router(event_type: str, payload: dict[str, Any]) -> None:
        await route_payment_event(event_type, payload, resources.publisher)

    return OutboxRelay(
        session_manager=resources.database,
        event_router=event_router,
        logger=resources.logger,
        poll_interval=float(resources.settings.POLLING_INTERVAL_FROM_DB),
        outbox_model=OutboxEvent,
    )
