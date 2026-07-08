from logging import Logger
from uuid import UUID

from pydantic import EmailStr
from faststream.rabbit import RabbitExchange

from shared.shared_instances import logger, settings, rabbitmq_broker, inventory_exchange, supplier_exchange
from shared.events.event_publisher import BaseEventPublisher
from shared.settings import Settings
from shared.schemas.event_schemas import (
    InventoryReserveSucceeded,
    InventoryReserveFailed,
    SupplierProductImportSucceededEvent,
    SupplierProductImportFailedEvent,
)
from shared.schemas.order_schemas import OrderItemBase
from shared.enums.event_enums import SupplierEvents


class ProductEventPublisher(BaseEventPublisher):
    """Event publisher for Product Service using FastStream"""

    def __init__(self, logger: Logger, settings: Settings):
        super().__init__(rabbitmq_broker, logger, settings)
        self.inventory_exchange: RabbitExchange = inventory_exchange
        self.supplier_exchange: RabbitExchange = supplier_exchange

    async def publish_inventory_reserve_succeeded(self,
                                                  order_id: UUID,
                                                  user_id: UUID,
                                                  reserved_items: list[OrderItemBase],
                                                  user_email: EmailStr):
        """Notify Order Service that inventory reservation succeeded"""
        event = InventoryReserveSucceeded(
            user_id=user_id,
            user_email=user_email,
            order_id=order_id,
            reserved_items=reserved_items
        )
        await self.publish_an_event(event=event, exchange=self.inventory_exchange, routing_key=event.event_type)
        self.logger.info(f"Published inventory reserve succeeded event for order id: {event.order_id}")

    async def publish_inventory_reserve_failed(self,
                                              order_id: UUID,
                                              user_id: UUID,
                                              reasons: str,
                                              failed_items: list[OrderItemBase],
                                              user_email: EmailStr):
        """Notify Order Service that inventory reservation failed"""
        event = InventoryReserveFailed(
            user_id=user_id,
            user_email=user_email,
            order_id=order_id,
            reasons=reasons,
            failed_items=failed_items
        )
        await self.publish_an_event(event=event, exchange=self.inventory_exchange, routing_key=event.event_type)
        self.logger.info(f"Published inventory reserve failed event for order id: {event.order_id}")

    async def publish_supplier_product_import_succeeded(self, event: SupplierProductImportSucceededEvent):
        """Notify supplier_service that products were imported successfully."""
        await self.publish_an_event(
            event=event,
            exchange=self.supplier_exchange,
            routing_key=SupplierEvents.SUPPLIER_PRODUCT_IMPORT_SUCCEEDED,
        )
        self.logger.info(f"Published supplier product import succeeded event for fetch_id: {event.fetch_id}")

    async def publish_supplier_product_import_failed(self, event: SupplierProductImportFailedEvent):
        """Notify supplier_service that product import failed."""
        await self.publish_an_event(
            event=event,
            exchange=self.supplier_exchange,
            routing_key=SupplierEvents.SUPPLIER_PRODUCT_IMPORT_FAILED,
        )
        self.logger.info(f"Published supplier product import failed event for fetch_id: {event.fetch_id}")


product_event_publisher = ProductEventPublisher(logger=logger, settings=settings)
