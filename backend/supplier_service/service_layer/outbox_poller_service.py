from typing import Any
from logging import Logger

from shared.outbox import OutboxRelay
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.enums.event_enums import SupplierEvents, OrderEvents
from event_publisher.supplier_event_publisher import SupplierEventPublisher
from models.outbox_models import OutboxEvent


def build_outbox_relay(
    database: DatabaseSessionManager,
    publisher: SupplierEventPublisher,
    logger: Logger,
    poll_interval: float,
) -> OutboxRelay:
    async def route_supplier_event(event_type: str, payload: dict[str, Any]) -> None:
        routes = {
            SupplierEvents.SUPPLIER_PRODUCTS_FETCHED: publisher.publish_supplier_products_fetched,
            OrderEvents.CJ_ORDER_CREATED: publisher.publish_cj_order_created,
            OrderEvents.CJ_ORDER_FAILED: publisher.publish_cj_order_failed,
        }
        publish = routes.get(event_type)
        if publish is None:
            raise ValueError(f"Unsupported supplier outbox event type: {event_type}")
        await publish(payload)

    return OutboxRelay(
        session_manager=database,
        event_router=route_supplier_event,
        logger=logger,
        poll_interval=poll_interval,
        outbox_model=OutboxEvent,
    )
