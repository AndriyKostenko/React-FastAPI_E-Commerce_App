from typing import Any

from shared.outbox import OutboxRelay
from shared.enums.event_enums import SupplierEvents, OrderEvents
from models.outbox_models import OutboxEvent
from resources import SupplierOutboxResources


def build_outbox_relay(resources: SupplierOutboxResources) -> OutboxRelay:
    publisher = resources.publisher

    async def route_supplier_event(event_type: str, payload: dict[str, Any]) -> None:
        routes = {
            SupplierEvents.SUPPLIER_PRODUCTS_FETCHED: publisher.publish_supplier_products_fetched,
            OrderEvents.CJ_ORDER_CREATED: publisher.publish_cj_order_created,
            OrderEvents.CJ_ORDER_FAILED: publisher.publish_cj_order_failed,
            OrderEvents.CJ_ORDER_PAID: publisher.publish_cj_order_paid,
            OrderEvents.CJ_ORDER_SHIPPED: publisher.publish_cj_order_shipped,
            OrderEvents.CJ_ORDER_DELIVERED: publisher.publish_cj_order_delivered,
        }
        publish = routes.get(event_type)
        if publish is None:
            raise ValueError(f"Unsupported supplier outbox event type: {event_type}")
        await publish(payload)

    return OutboxRelay(
        session_manager=resources.database,
        event_router=route_supplier_event,
        logger=resources.logger,
        poll_interval=float(resources.settings.POLLING_INTERVAL_FROM_DB),
        outbox_model=OutboxEvent,
    )
