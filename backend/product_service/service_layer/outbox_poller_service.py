from logging import Logger
from typing import Any

from event_publisher.event_publisher import ProductEventPublisher
from models.outbox_models import OutboxEvent
from shared.enums.event_enums import InventoryEvents, SupplierEvents
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.outbox import OutboxRelay
from shared.contracts.events import InventoryReserveFailed, InventoryReserveSucceeded


def build_outbox_relay(
    database: DatabaseSessionManager,
    publisher: ProductEventPublisher,
    logger: Logger,
    poll_interval: float,
) -> OutboxRelay:
    async def route_product_event(event_type: str, payload: dict[str, Any]) -> None:
        if event_type == InventoryEvents.INVENTORY_RESERVE_SUCCEEDED:
            event = InventoryReserveSucceeded(**payload)
            await publisher.publish_inventory_reserve_succeeded(
                order_id=event.order_id,
                user_id=event.user_id,
                user_email=event.user_email,
                reserved_items=event.reserved_items,
            )
            return
        if event_type == InventoryEvents.INVENTORY_RESERVE_FAILED:
            event = InventoryReserveFailed(**payload)
            await publisher.publish_inventory_reserve_failed(
                order_id=event.order_id,
                user_id=event.user_id,
                user_email=event.user_email,
                reasons=event.reasons,
                failed_items=event.failed_items,
            )
            return
        if event_type == SupplierEvents.SUPPLIER_PRODUCT_IMPORT_COMPLETED:
            from shared.contracts.events import SupplierProductImportCompletedEvent

            await publisher.publish_supplier_product_import_completed(
                SupplierProductImportCompletedEvent(**payload)
            )
            return
        if event_type == SupplierEvents.SUPPLIER_PRODUCT_IMPORT_FAILED:
            from shared.contracts.events import SupplierProductImportFailedEvent

            await publisher.publish_supplier_product_import_failed(
                SupplierProductImportFailedEvent(**payload)
            )
            return
        raise ValueError(f"Unsupported product outbox event type: {event_type}")

    return OutboxRelay(
        session_manager=database,
        event_router=route_product_event,
        logger=logger,
        poll_interval=poll_interval,
        outbox_model=OutboxEvent,
    )
