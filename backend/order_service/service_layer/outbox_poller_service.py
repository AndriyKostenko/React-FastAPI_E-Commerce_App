from typing import Any

from shared.outbox import OutboxRelay
from shared.enums.event_enums import InventoryEvents, OrderEvents
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
