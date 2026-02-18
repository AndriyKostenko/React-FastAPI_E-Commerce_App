from logging import Logger
from typing import Any

from database_layer.order_address_repository import OrderAddressRepository
from database_layer.order_item_repository import OrderItemRepository
from database_layer.order_repository import OrderRepository
from events_publisher.order_event_publisher import order_event_publisher
from service_layer.order_address_service import OrderAddressService
from service_layer.order_item_service import OrderItemService
from shared.schemas.event_schemas import InventoryReserveFailed, InventoryReserveSucceeded
from shared.shared_instances import logger, order_service_database_session_manager
from service_layer.order_service import OrderService, OrderStatus

"""
Order Event Consumer - SAGA Orchestrator
This consumer listens to events from other services (primarily Product Service)
and orchestrates the Order SAGA workflow:

1. When inventory reservation succeeds -> Confirm the order
2. When inventory reservation fails -> Cancel the order and trigger compensation

The FastStream app will be executed via `faststream run`, so no manual uvicorn setup is needed.
"""


class OrderEventConsumer:
    """
    Business logic handler for Order SAGA orchestration.
    This class handles the actual business logic, while the subscriber functions
    handle the FastStream integration.
    """
    def __init__(self, logger: Logger):
        self.logger: Logger = logger

    async def _get_order_service(self):
        """
        Creating an OrderService instance with a fresh database session.
        This is similar to FastAPI's dependency injection but for FastStream consumers.
        """
        async with order_service_database_session_manager.transaction() as session:
            order_item_service = OrderItemService(
                repository=OrderItemRepository(session=session)
            )
            order_address_service = OrderAddressService(
                repository=OrderAddressRepository(session=session)
            )
            order_service = OrderService(
                repository=OrderRepository(session=session),
                order_item_service=order_item_service,
                order_address_service=order_address_service
            )
            yield order_service

    async def handle_order_saga_response(self, message: dict[str, Any]):
        """
        Route SAGA responses to appropriate handlers based on event type.
        """
        event_type = message.get("event_type")
        match event_type:
            case "inventory.reserve.succeeded":
                await self.handle_inventory_reserve_succeeded(message)
            case "inventory.reserve.failed":
                await self.handle_inventory_reserve_failed(message)
            case _:
                self.logger.warning(f"Unhandled SAGA event type: {event_type}")

    async def handle_inventory_reserve_succeeded(self, message: dict[str, Any]):
        """
        Handle successful inventory reservation.

        Steps:
        1. Parse the event
        2. Update order status to CONFIRMED in database
        3. Publish OrderConfirmedEvent for downstream services (e.g., notification / payments)
        """
        try:
            # Parse the event
            event = InventoryReserveSucceeded(**message)
            self.logger.info(f"Inventory reservation succeeded for order id: {event.order_id}")

            # Get order service with database session
            async for order_service in self._get_order_service():
                # Update order status to CONFIRMED
                await order_service.update_order_status(
                    order_id=event.order_id,
                    order_status=OrderStatus.CONFIRMED
                )
                self.logger.info(f"Updated status to: {OrderStatus.CONFIRMED} for order id: {event.order_id}")

            # Publish OrderConfirmedEvent for downstream services (notification, etc.)
            await order_event_publisher.publish_order_confirmed(
                order_id=event.order_id,
                user_id=event.user_id
            )
            self.logger.info(f"Published OrderConfirmedEvent for order {event.order_id}")

            # TODO: notification service/payment services events -> ...

        except Exception as e:
            self.logger.error(f"Error handling inventory reserve succeeded for order {message.get('order_id')}: {str(e)}")
            raise

    async def handle_inventory_reserve_failed(self, message: dict[str, Any]):
        """
        Handle failed inventory reservation (SAGA Compensation).

        Steps:
        1. Parse the event
        2. Update order status to CANCELLED in database
        3. Publish OrderCancelledEvent for downstream services
        4. No need to release inventory since it was never reserved
        """
        try:
            # Parse the event
            event = InventoryReserveFailed(**message)
            self.logger.info(f"Inventory reservation failed for order {event.order_id}: {event.reasons}")

            # Get order service with database session
            async for order_service in self._get_order_service():
                # Update order status to CANCELLED
                await order_service.update_order_status(  # pyright: ignore[reportUnusedCallResult]
                    order_id=event.order_id,
                    order_status=OrderStatus.CANCELLED
                )
                self.logger.info(f"Updated status to {OrderStatus.CANCELLED} for order id: {event.order_id}")

            # Publish OrderCancelledEvent for downstream services (notification, etc.)
            await order_event_publisher.publish_order_cancelled(
                order_id=event.order_id,
                user_id=event.user_id,
                reason=event.reasons
            )
            self.logger.info(f"Published OrderCancelledEvent for order {event.order_id}")

            # TODO: notification service/payment services events -> ...

        except Exception as e:
            self.logger.error(f"Error handling inventory reserve failed for order {message.get('order_id')}: {str(e)}")
            raise


# Create consumer instance
order_event_consumer = OrderEventConsumer(logger=logger)
