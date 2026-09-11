from typing import Any

from shared.outbox import OutboxRelay
from shared.enums.event_enums import (
    ArtworkEvents,
    InventoryEvents,
    OrderEvents,
    PaymentCommands,
    ProductionEvents,
)
from events_publisher.order_event_publisher import OrderEventPublisher
from models.outbox_models import OutboxEvent
from resources import OrderOutboxResources


async def route_order_event(
    event_type: str,
    payload: dict[str, Any],
    publisher: OrderEventPublisher,
) -> None:
    routes = {
        OrderEvents.ORDER_CREATED: publisher.publish_order_created,
        OrderEvents.ORDER_CONFIRMED: publisher.publish_order_confirmed,
        OrderEvents.ORDER_CANCELLED: publisher.publish_order_cancelled,
        InventoryEvents.INVENTORY_RESERVE_REQUESTED: publisher.publish_inventory_reserve_requested,
        InventoryEvents.INVENTORY_RELEASE_REQUESTED: publisher.publish_inventory_release_requested,
        ProductionEvents.PRODUCTION_JOB_STARTED: publisher.publish_production_job_started,
        ProductionEvents.PRODUCTION_JOB_PRINTED: publisher.publish_production_job_printed,
        ProductionEvents.PRODUCTION_JOB_SHIPPED: publisher.publish_production_job_shipped,
        ProductionEvents.PRODUCTION_JOB_DELIVERED: publisher.publish_production_job_delivered,
        ProductionEvents.PRODUCTION_JOB_CANCELLED: publisher.publish_production_job_cancelled,
        ArtworkEvents.ARTWORK_RETAINED: publisher.publish_artwork_retained,
        ArtworkEvents.ARTWORK_RELEASED: publisher.publish_artwork_released,
        PaymentCommands.CAPTURE_REQUESTED: publisher.publish_payment_capture_requested,
        PaymentCommands.RELEASE_REQUESTED: publisher.publish_payment_release_requested,
    }
    publish = routes.get(event_type)
    if not publish:
        raise ValueError(f"Unsupported order outbox event type: {event_type}")
    await publish(payload)


def build_outbox_relay(resources: OrderOutboxResources) -> OutboxRelay:
    async def event_router(event_type: str, payload: dict[str, Any]) -> None:
        await route_order_event(event_type, payload, resources.publisher)

    return OutboxRelay(
        session_manager=resources.database,
        event_router=event_router,
        logger=resources.logger,
        poll_interval=float(resources.settings.POLLING_INTERVAL_FROM_DB),
        outbox_model=OutboxEvent,
    )
