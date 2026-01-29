from logging import Logger
from uuid import UUID, uuid4
from datetime import datetime, timezone

from faststream.rabbit import RabbitQueue

from shared.shared_instances import logger, settings, broker
from shared.event_publisher import BaseEventPublisher
from shared.settings import Settings
from shared.schemas.event_schemas import (
    InventoryReserveSucceeded,
    InventoryReserveFailed,
)
from shared.schemas.order_schemas import OrderItemBase


class ProductEventPublisher(BaseEventPublisher):
    """Event publisher for Product Service using FastStream"""

    def __init__(self, logger: Logger, settings: Settings):
        super().__init__(broker, logger, settings)
        self.order_saga_response_queue: RabbitQueue = RabbitQueue("order.saga.response", durable=True)

    async def publish_inventory_reserve_succeeded(self,
                                                  order_id: UUID,
                                                  user_id: UUID,
                                                  reserved_items: list[OrderItemBase]):
        """Notify Order Service that inventory reservation succeeded"""
        event = InventoryReserveSucceeded(
            event_id=uuid4(),
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            service="product-service",
            event_type="inventory.reserve.succeeded",
            order_id=order_id,
            reserved_items=reserved_items
        )
        await self.publish_an_event(
            message=event,
            queue=self.order_saga_response_queue
        )

    async def publish_inventory_reserve_failed(self,
                                              order_id: UUID,
                                              user_id: UUID,
                                              reasons: str,
                                              failed_items: list[OrderItemBase]):
        """Notify Order Service that inventory reservation failed"""
        event = InventoryReserveFailed(
            event_id=uuid4(),
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            service="product-service",
            event_type="inventory.reserve.failed",
            order_id=order_id,
            reasons=reasons,
            failed_items=failed_items
        )
        await self.publish_an_event(
            message=event,
            queue=self.order_saga_response_queue
        )


product_event_publisher = ProductEventPublisher(logger=logger, settings=settings)
