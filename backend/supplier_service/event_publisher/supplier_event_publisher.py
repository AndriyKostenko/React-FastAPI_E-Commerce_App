from logging import Logger
from typing import Any

from faststream.rabbit import RabbitExchange

from shared.shared_instances import (
    inventory_exchange,
    logger,
    order_exchange,
    rabbitmq_broker,
    settings,
    supplier_exchange,
)
from shared.events.event_publisher import BaseEventPublisher
from shared.settings import Settings
from shared.schemas.event_schemas import (
    CJOrderCreatedEvent,
    InventoryReleaseRequested,
    OrderCancelledEvent,
    SupplierProductsFetchedEvent,
)
from shared.enums.event_enums import InventoryEvents, OrderEvents, SupplierEvents


class SupplierEventPublisher(BaseEventPublisher):
    """Event publisher for supplier_service using FastStream."""

    def __init__(self, logger: Logger, settings: Settings):
        super().__init__(rabbitmq_broker, logger, settings)
        self.exchange: RabbitExchange = supplier_exchange
        self.order_exchange: RabbitExchange = order_exchange
        self.inventory_exchange: RabbitExchange = inventory_exchange

    async def publish_supplier_products_fetched(self, event_data: dict[str, Any]) -> None:
        """Publish a SupplierProductsFetched event to RabbitMQ."""
        event = SupplierProductsFetchedEvent(**event_data)
        await self.publish_an_event(
            event=event,
            exchange=self.exchange,
            routing_key=SupplierEvents.SUPPLIER_PRODUCTS_FETCHED,
        )
        self.logger.info(f"Published supplier products fetched event for supplier: {event.supplier_id}, fetch_id: {event.fetch_id}")

    async def publish_cj_order_created(self, event_data: dict[str, Any]) -> None:
        """Publish a CJOrderCreatedEvent to the order events exchange."""
        event = CJOrderCreatedEvent(**event_data)
        await self.publish_an_event(
            event=event,
            exchange=self.order_exchange,
            routing_key=OrderEvents.CJ_ORDER_CREATED,
        )
        self.logger.info(f"Published CJOrderCreatedEvent for order: {event.order_id}")

    async def publish_order_cancelled(self, event_data: dict[str, Any]) -> None:
        """Publish an OrderCancelledEvent to the order events exchange."""
        event = OrderCancelledEvent(**event_data)
        await self.publish_an_event(
            event=event,
            exchange=self.order_exchange,
            routing_key=OrderEvents.ORDER_CANCELLED,
        )
        self.logger.info(f"Published OrderCancelledEvent for order: {event.order_id}")

    async def publish_inventory_release_requested(self, event_data: dict[str, Any]) -> None:
        """Publish an InventoryReleaseRequested event to the inventory exchange."""
        event = InventoryReleaseRequested(**event_data)
        await self.publish_an_event(
            event=event,
            exchange=self.inventory_exchange,
            routing_key=InventoryEvents.INVENTORY_RELEASE_REQUESTED,
        )
        self.logger.info(f"Published InventoryReleaseRequested for order: {event.order_id}")


supplier_event_publisher = SupplierEventPublisher(logger=logger, settings=settings)
