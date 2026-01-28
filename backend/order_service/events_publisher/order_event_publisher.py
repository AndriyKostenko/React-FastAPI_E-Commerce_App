from uuid import UUID, uuid4
from datetime import datetime, timezone
from logging import Logger

from pydantic import PositiveFloat
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
from shared.schemas.order_schemas import OrderItemBase


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
            "inventory.events",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "inventory.events.dlq"
            }
        )

    async def publish_order_created(self,
                                    order_id: UUID,
                                    user_id: UUID,
                                    items: list[OrderItemBase],
                                    total_amount: PositiveFloat):
        """Publish order created event (SAGA start)"""
        event = OrderCreatedEvent(
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            service="order-service",
            event_type="order.created",
            order_id=order_id,
            user_id=user_id,
            items=items,
            total_amount=total_amount
        )
        await self.publish_an_event(
            message=event,
            queue=self.order_events_queue
        )
        self.logger.info(f"Published OrderCreatedEvent for order {order_id}")

    async def publish_inventory_reserve_requested(self,
                                                  order_id: UUID,
                                                  user_id: UUID,
                                                  items: list[OrderItemBase]):
        """Request inventory reservation from Product Service"""
        event = InventoryReserveRequested(
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            service="order-service",
            event_type="inventory.reserve.requested",
            order_id=order_id,
            user_id=user_id,
            items=items
        )
        await self.publish_an_event(
            message=event,
            queue=self.inventory_events_queue
        )
        self.logger.info(f"Published InventoryReserveRequested for order {order_id}")

    async def publish_order_confirmed(self, order_id: UUID, user_id: UUID):
        """Publish order confirmed event (SAGA success)"""
        event = OrderConfirmedEvent(
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            service="order-service",
            event_type="order.confirmed",
            order_id=order_id,
            user_id=user_id
        )
        await self.publish_an_event(
            message=event,
            queue=self.order_events_queue
        )
        self.logger.info(f"Published OrderConfirmedEvent for order {order_id}")

    async def publish_order_cancelled(self, order_id: UUID, user_id: UUID, reason: str):
        """Publish order cancelled event (SAGA compensation)"""
        event = OrderCancelledEvent(
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            service="order-service",
            event_type="order.cancelled",
            order_id=order_id,
            user_id=user_id,
            reason=reason
        )
        await self.publish_an_event(
            message=event,
            queue=self.order_events_queue
        )
        self.logger.info(f"Published OrderCancelledEvent for order {order_id}: {reason}")

    async def publish_inventory_release_requested(self,
                                                  order_id: UUID,
                                                  user_id: UUID,
                                                  items: list[OrderItemBase],
                                                  reason: str):
        """Request inventory release (compensation transaction)"""
        event = InventoryReleaseRequested(
            event_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            service="order-service",
            event_type="inventory.release.requested",
            order_id=order_id,
            user_id=user_id,
            items=items,
            reason=reason
        )
        await self.publish_an_event(
            message=event,
            queue=self.inventory_events_queue
        )
        self.logger.info(f"Published InventoryReleaseRequested for order {order_id}: {reason}")


order_event_publisher = OrderEventPublisher(logger=logger, settings=settings)
