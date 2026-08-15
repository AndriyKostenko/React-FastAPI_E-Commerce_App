from typing import Any
from logging import Logger

from shared.outbox import OutboxRelay
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.enums.event_enums import SupplierEvents
from event_publisher.supplier_event_publisher import SupplierEventPublisher
from models.outbox_models import OutboxEvent


def build_outbox_relay(
    database: DatabaseSessionManager,
    publisher: SupplierEventPublisher,
    logger: Logger,
    poll_interval: float,
) -> OutboxRelay:
    async def route_supplier_event(event_type: str, payload: dict[str, Any]) -> None:
        if event_type != SupplierEvents.SUPPLIER_PRODUCTS_FETCHED:
            raise ValueError(f"Unsupported supplier outbox event type: {event_type}")
        await publisher.publish_supplier_products_fetched(payload)

    return OutboxRelay(
        session_manager=database,
        event_router=route_supplier_event,
        logger=logger,
        poll_interval=poll_interval,
        outbox_model=OutboxEvent,
    )
