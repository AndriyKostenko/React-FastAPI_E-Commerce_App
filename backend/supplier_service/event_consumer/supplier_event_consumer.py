from logging import Logger
from typing import Any

from database_layer.supplier_sync_state_repository import SupplierSyncStateRepository
from shared.enums.event_enums import SupplierEvents
from shared.shared_instances import logger, supplier_service_database_session_manager


class SupplierEventConsumer:
    """Consumer for supplier_service events, primarily import feedback from product_service."""

    def __init__(self, logger: Logger) -> None:
        self.logger: Logger = logger

    async def _get_sync_state_repository(self):
        async with supplier_service_database_session_manager.transaction() as session:
            yield SupplierSyncStateRepository(session=session)

    async def handle_import_feedback_event(self, message: dict[str, Any]) -> None:
        event_type = message.get("event_type")
        match event_type:
            case SupplierEvents.SUPPLIER_PRODUCT_IMPORT_SUCCEEDED:
                self.logger.info(
                    f"Product import succeeded for supplier {message.get('supplier_id')}, "
                    f"fetch_id {message.get('fetch_id')}: "
                    f"imported={message.get('imported')}, updated={message.get('updated')}, failed={message.get('failed')}"
                )
            case SupplierEvents.SUPPLIER_PRODUCT_IMPORT_FAILED:
                self.logger.error(
                    f"Product import failed for supplier {message.get('supplier_id')}, "
                    f"fetch_id {message.get('fetch_id')}: {message.get('reason')}"
                )
            case _:
                self.logger.warning(f"Unhandled supplier feedback event type: {event_type}")


supplier_event_consumer = SupplierEventConsumer(logger=logger)
