from logging import Logger
from uuid import UUID

from faststream.rabbit import RabbitQueue
from pydantic import EmailStr

from shared.shared_instances import logger, settings, broker
from shared.event_publisher import BaseEventPublisher
from shared.settings import Settings
from shared.schemas.event_schemas import (
    InventoryReserveSucceeded,
    InventoryReserveFailed,
)
from shared.schemas.order_schemas import OrderItemBase
from shared.enums.event_enums import OrderSagaResponseQueue


class ProductEventPublisher(BaseEventPublisher):
    """Event publisher for Product Service using FastStream"""

    def __init__(self, logger: Logger, settings: Settings):
        super().__init__(broker, logger, settings)
        # TODO: check if that's the correctly created a separate queue ?
        self.order_saga_response_queue: RabbitQueue = RabbitQueue(
            OrderSagaResponseQueue.ORDER_SAGA_RESPONSE_QUEUE,
            durable=True,
            arguments={
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": OrderSagaResponseQueue.ORDER_SAGA_RESPONSE_DEAD_LETTER_QUEUE
            }
        )

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
        await self.publish_an_event(message=event,queue=self.order_saga_response_queue)
        self.logger.info(f"Publihing inventory reserve succeedded event for order id: {event.order_id}")

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
        await self.publish_an_event(message=event,queue=self.order_saga_response_queue)
        self.logger.info(f"Publishing inventory reserve failed event for order id:{event.order_id}")


product_event_publisher = ProductEventPublisher(logger=logger, settings=settings)
