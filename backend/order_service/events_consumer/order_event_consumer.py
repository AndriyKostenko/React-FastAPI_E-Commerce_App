from logging import Logger
from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitQueue, RabbitBroker

from events_publisher.order_event_publisher import order_event_publisher
from shared.schemas.event_schemas import InventoryReserveFailed, InventoryReserveSucceeded
from shared.shared_instances import broker, logger
from dependencies.dependencies import order_service_dependency
from service_layer.order_service import OrderStatus

"""
Order Event Consumer - SAGA Orchestrator

This consumer listens to events from other services (primarily Product Service)
and orchestrates the Order SAGA workflow:

1. When inventory reservation succeeds -> Confirm the order
2. When inventory reservation fails -> Cancel the order and trigger compensation

The FastStream app will be executed via `faststream run`, so no manual uvicorn setup is needed.
"""


app = FastStream(broker)


class OrderEventConsumer:
    """
    Handle SAGA orchestration responses from other services

    This is the central coordinator for the order SAGA pattern.
    It receives responses from services like Product Service and decides
    whether to proceed with order confirmation or trigger compensation.
    """
    def __init__(self):
        self.broker: RabbitBroker = broker
        self.logger: Logger = logger
        self.order_service = ...

        # Define the queue for SAGA responses from other services
        self.order_saga_response_queue: RabbitQueue = RabbitQueue(
            "order.saga.response",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "order.saga.response.dlq"
            }
        )

    @self.broker.subscriber(queue=self.order_saga_response_queue, retry=3)
    async def handle_saga_responses(self, message: dict[str, Any]):
        """
        Handle SAGA orchestration responses from other services

        This is the central coordinator for the order SAGA pattern.
        It receives responses from services like Product Service and decides
        whether to proceed with order confirmation or trigger compensation.
        """
        event_type = message.get("event_type")
        match event_type:
            case "inventory.reserve.succedded":
                await self._handle_inventory_reserve_suceeded(message)

            case "inventory.reserve.failer":
                await self._handle_inventory_reserve_failed(message)
            case _:
                self.logger.warning(f"Unhandled SAGA event type: {event_type}")

    async def _handle_inventory_reserve_suceeded(self, message):
        """
        Handle successful inventory reservation

        Steps:
        1. Parse the event
        2. Update order status to CONFIRMED in database
        3. Publish OrderConfirmedEvent for downstream services (e.g., notification)
        4. Payment???
        """
        # getting an event
        event = InventoryReserveSucceeded(**message)
        self.logger.info(f"Inventory reservation succeeded for order id: {event.order_id}")

        # updating order status in db
        await order_service_dependency.update_order_status(order_id=event.order_id, order_status=OrderStatus.CONFIRMED)
        self.logger.info(f"Updated status: {OrderStatus.CONFIRMED} for order id: {event.order_id}")

        # publishing an order confirmed for downstream events
        await order_event_publisher.publish_order_confirmed(
            order_id=event.order_id,
            user_id=event.user_id
        )

        # Payment & Notification..

    async def _handle_inventory_reserve_failed(self, message):
        """
        Handle failed inventory reservation (SAGA Compensation)

        Steps:
        1. Parse the event
        2. Update order status to CANCELLED in database
        3. Publish OrderCancelledEvent for downstream services
        4. No need to release inventory since it was never reserved
        """
        # getting an event
        event = InventoryReserveFailed(**message)
        self.logger.info(f"Inventory reservation failed for order {event.order_id}: {event.reason}")

        # updating order status in db
        await order_service_dependency.update_order_status(order_id=event.order_id, order_status=OrderStatus.CANCELLED)

        # Publish order cancelled event for downstream services
        # This will notify user about the cancellation
        await order_event_publisher.publish_order_cancelled(
            order_id=event.order_id,
            user_id=event.user_id,
            reason=event.reason
        )

        # Payment & Notification..
