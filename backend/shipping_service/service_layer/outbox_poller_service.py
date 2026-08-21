from typing import Any

from events_publisher.shipping_event_publisher import ShippingEventPublisher
from models.outbox_models import OutboxEvent
from shared.enums.event_enums import ShippingEvents
from shared.outbox import OutboxRelay
from shared.managers.database_session_manager import DatabaseSessionManager


def build_outbox_relay(database: DatabaseSessionManager, publisher: ShippingEventPublisher, logger, poll_interval: float):
    async def route(event_type: str, payload: dict[str, Any]) -> None:
        routes = {
            ShippingEvents.SHIPMENT_CREATED: publisher.publish_shipment_created,
            ShippingEvents.SHIPMENT_SHIPPED: publisher.publish_shipment_shipped,
            ShippingEvents.SHIPMENT_DELIVERED: publisher.publish_shipment_delivered,
            ShippingEvents.SHIPMENT_CANCELLED: publisher.publish_shipment_cancelled,
        }
        publish = routes.get(event_type)
        if publish is None:
            raise ValueError(f"Unsupported shipping outbox event type: {event_type}")
        await publish(payload)

    return OutboxRelay(
        session_manager=database,
        event_router=route,
        logger=logger,
        poll_interval=poll_interval,
        outbox_model=OutboxEvent,
    )

