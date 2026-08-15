from typing import Any
from logging import Logger

from faststream.rabbit import RabbitBroker, RabbitExchange

from shared.settings import Settings
from shared.events.event_publisher import BaseEventPublisher
from messaging import inventory_exchange, order_exchange
from shared.contracts.events import (
    OrderCreatedEvent,
    OrderCancelledEvent,
    OrderConfirmedEvent,
    InventoryReserveRequested,
    InventoryReleaseRequested,
)


class OrderEventPublisher(BaseEventPublisher):
    """Event publisher for Order Service using FastStream"""
    def __init__(
        self,
        rabbitmq_broker: RabbitBroker,
        logger: Logger,
        settings: Settings,
    ) -> None:
        super().__init__(rabbitmq_broker, logger, settings)
        self.order_exchange: RabbitExchange = order_exchange
        self.inventory_exchange: RabbitExchange = inventory_exchange

    async def publish_order_created(self, event_data: dict[str, Any]):
        """Publish order created event (SAGA start)"""
        event = OrderCreatedEvent(**event_data)
        await self.publish_an_event(event=event, exchange=self.order_exchange, routing_key=event.event_type)
        self.logger.info(f"Published OrderCreatedEvent for order {event.order_id}")

    async def publish_inventory_reserve_requested(self, event_data: dict[str, Any]):
        """Request inventory reservation from Product Service"""
        event = InventoryReserveRequested(**event_data)
        await self.publish_an_event(event=event, exchange=self.inventory_exchange, routing_key=event.event_type)
        self.logger.info(f"Published InventoryReserveRequested for order: {event.order_id}")

    async def publish_order_confirmed(self, event_data: dict[str, Any]):
        """Publish order confirmed event (SAGA success)"""
        event = OrderConfirmedEvent(**event_data)
        await self.publish_an_event(event=event, exchange=self.order_exchange, routing_key=event.event_type)
        self.logger.info(f"Published OrderConfirmedEvent for order {event.order_id}")

    async def publish_order_cancelled(self, event_data: dict[str, Any]):
        """Publish order cancelled event (SAGA compensation)"""
        event = OrderCancelledEvent(**event_data)
        await self.publish_an_event(event=event, exchange=self.order_exchange, routing_key=event.event_type)
        self.logger.info(f"Published OrderCancelledEvent for order: {event.order_id}: {event.reason}")

    async def publish_inventory_release_requested(self, event_data: dict[str, Any]):
        """Request inventory release (compensation transaction)"""
        event = InventoryReleaseRequested(**event_data)
        await self.publish_an_event(event=event, exchange=self.inventory_exchange, routing_key=event.event_type)
        self.logger.info(f"Published InventoryReleaseRequested for order: {event.order_id}: {event.reason}")
