from typing import Any

from models.outbox_models import OutboxEvent
from resources import ShippingOutboxResources
from shared.enums.event_enums import ShippingEvents
from shared.outbox import OutboxRelay


def build_outbox_relay(resources: ShippingOutboxResources) -> OutboxRelay:
    publisher = resources.publisher

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
        session_manager=resources.database,
        event_router=route,
        logger=resources.logger,
        poll_interval=float(resources.settings.POLLING_INTERVAL_FROM_DB),
        outbox_model=OutboxEvent,
    )
