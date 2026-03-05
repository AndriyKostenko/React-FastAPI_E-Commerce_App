from typing import Any
from logging import Logger

from faststream.rabbit import RabbitQueue

from shared.settings import Settings
from shared.event_publisher import BaseEventPublisher
from shared.shared_instances import settings, logger, broker
from shared.schemas.event_schemas import (
    OrderCreatedEvent,
    OrderCancelledEvent,
    OrderConfirmedEvent,
    InventoryReserveRequested,
    InventoryReleaseRequested,
)


class OrderEventPublisher(BaseEventPublisher):
    """Event publisher for Order Service using FastStream"""
    def __init__(self, logger: Logger, settings: Settings):
        super().__init__(broker, logger, settings)
        # Queue definitions with dead-letter configuration
        self.order_events_queue: RabbitQueue = RabbitQueue(
            "order.events",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "order.events.dlq"
            }
        )
        self.inventory_events_queue: RabbitQueue = RabbitQueue(
            "product.inventory.events",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "inventory.events.dlq"
            }
        )

    async def publish_order_created(self, event_data: dict[str, Any]):
        """Publish order created event (SAGA start)"""
        event = OrderCreatedEvent(**event_data)
        await self.publish_an_event(
            message= event,
            queue=self.order_events_queue
        )
        self.logger.info(f"Published OrderCreatedEvent for order {event.order_id}")

    async def publish_inventory_reserve_requested(self, event_data: dict[str, Any]):
        """Request inventory reservation from Product Service"""
        event = InventoryReserveRequested(**event_data)
        await self.publish_an_event(
            message=event,
            queue=self.inventory_events_queue
        )
        self.logger.info(f"Published InventoryReserveRequested for order: {event.order_id}")

    async def publish_order_confirmed(self, event_data: dict[str, Any]):
        """Publish order confirmed event (SAGA success)"""
        event = OrderConfirmedEvent(**event_data)
        await self.publish_an_event(
            message=event,
            queue=self.order_events_queue
        )
        self.logger.info(f"Published OrderConfirmedEvent for order {event.order_id}")

    async def publish_order_cancelled(self, event_data: dict[str, Any]):
        """Publish order cancelled event (SAGA compensation)"""
        event = OrderCancelledEvent(**event_data)
        await self.publish_an_event(
            message=event,
            queue=self.order_events_queue
        )
        self.logger.info(f"Published OrderCancelledEvent for order: {event.order_id}: {event.reason}")

    async def publish_inventory_release_requested(self, event_data: dict[str, Any]):
        """Request inventory release (compensation transaction)"""
        event = InventoryReleaseRequested(**event_data)
        await self.publish_an_event(
            message=event,
            queue=self.inventory_events_queue
        )
        self.logger.info(f"Published InventoryReleaseRequested for order: {event.order_id}: {event.reason}")


order_event_publisher = OrderEventPublisher(logger=logger, settings=settings)
