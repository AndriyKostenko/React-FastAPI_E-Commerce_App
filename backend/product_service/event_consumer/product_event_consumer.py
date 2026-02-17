from logging import Logger
from typing import Any

from database_layer.product_image_repository import ProductImageRepository
from database_layer.product_repository import ProductRepository
from exceptions.product_exceptions import ProductReleaseError
from service_layer.product_service import ProductService
from service_layer.product_image_service import ProductImageService
from shared.schemas.event_schemas import InventoryReserveRequested, InventoryReleaseRequested
from shared.shared_instances import logger, product_service_database_session_manager, product_event_idempotency_service
from event_publisher.event_publisher import product_event_publisher
from shared.idempotency_service import IdempotencyEventService

"""
Product Event Consumer - SAGA Orchestrator
This consumer listens to events from other services (primarily Order Service)
and orchestrates the Order SAGA workflow:

1. Product Service receives InventoryReserveRequested
2. Product Service reserves inventory
3. Product Service publishes: InventoryReserveSucceeded (if not - InventoryReserveFailed)

The FastStream app will be executed via `faststream run`, so no manual uvicorn setup is needed.
"""


class ProductEventConsumer:
    def __init__(self, logger: Logger) -> None:
        self.logger: Logger = logger
        self.idempotency_service: IdempotencyEventService = product_event_idempotency_service

    async def _get_product_service(self):
        """
        Create a ProductService instance with a fresh database session.
        This mimics FastAPI's dependency injection but for FastStream consumers.
        """
        async with product_service_database_session_manager.transaction() as session:
            product_image_service = ProductImageService(
                repository=ProductImageRepository(session=session)
            )
            product_service = ProductService(
                repository=ProductRepository(session=session),
                product_image_service=product_image_service
            )
            yield product_service

    async def handle_inventory_saga_event(self, message: dict[str, Any]):
        """
        Route inventory events to appropriate handlers based on event type
        """
        event_type = message.get("event_type")
        match event_type:
            case "inventory.reserve.requested":
                await self.handle_inventory_reserve_requested(message)
            case "inventory.release.requested":
                await self.handle_inventory_release_requested(message)
            case _:
                self.logger.warning(f"Unhandled inventory event type: {event_type}")

    async def handle_inventory_reserve_requested(self, message: dict[str, Any]):
        """
        Handle inventory reservation request from Order Service.

        Steps:
        1. Parse the event
        2. Check if its saved in Redis
        3. Check if all products are available in sufficient quantities
        4. If yes: Reserve inventory and publish InventoryReserveSucceeded
        5. If no: Publish InventoryReserveFailed with details

        Business Rules:
        - All items must be available, otherwise the entire reservation fails (atomicity)
        - Products must be in stock (in_stock=True)
        - Quantity must be sufficient for each item
        """
        # 1.Parse the event
        event = InventoryReserveRequested(**message)
        try:
            # 2. checking idempotency FIRST - befoer any processing
            if await self.idempotency_service.is_event_processed(event.event_id, event.event_type)
                self.logger.info(f"Skipping duplicate inventory reservation for order: {event.order_id}")
                return # skipping coa already processed
            self.logger.info(f"Processing inventory reservation for order {event.order_id} with: {len(event.items)} items")
            # 3.getting product service with db session
            async for product_service in self._get_product_service():
                # 4.validating for sufficient quantity and successfull reservetion
                reserved_items = await product_service.reserve_inventory(event.items)
                if not reserved_items["success"]:
                    # marking as processed event even on failure
                    await self.idempotency_service.mark_event_as_processed(
                        event_id=event.event_id,
                        event_type=event.event_type,
                        order_id=event.order_id,
                        result="failed"
                    )
                    # inventory reserv failed, publishing failure event
                    await product_event_publisher.publish_inventory_reserve_failed(
                        order_id=event.order_id,
                        user_id=event.user_id,
                        user_email=event.user_email,
                        reasons=reserved_items["reasons"],
                        failed_items=reserved_items["failed_products"]
                    )
                    self.logger.warning(f"Inventory reservation failed for order: {str(event.order_id)} reasons: {reserved_items['reasons']}")
                    return
                await self.idempotency_service.mark_event_as_processed(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    order_id=event.order_id,
                    result="succeeded"
                )
                self.logger.info(f"Successfully reserved inventory for order: {event.order_id}")
                #5. publishing a success event to Order service
                await product_event_publisher.publish_inventory_reserve_succeeded(
                    order_id=event.order_id,
                    user_id=event.user_id,
                    user_email=event.user_email,
                    reserved_items=reserved_items["products"]
                )

        except Exception as error:
            # Critical error - log and publish failure event
            self.logger.error(f"Error handling inventory reserve request for order {event.order_id}: {str(error)}")
            await product_event_publisher.publish_inventory_reserve_failed(
                order_id=event.order_id,
                user_id=event.user_id,
                user_email=event.user_email,
                reasons=f"System error: {str(error)}",
                failed_items=event.items
            )
            raise

    async def handle_inventory_release_requested(self, message: dict[str, Any]):
        """
        Handle inventory release request (SAGA Compensation).

        This occurs when:
        - Order is cancelled by user
        - Payment fails after inventory was reserved
        - Order times out

        Steps:
        1. Parse the event
        2. Release inventory (increment quantities back)
        3. Log the release for audit purposes
        """
        # Parse the event
        event = InventoryReleaseRequested(**message)
        try:
            # checking idempotency (if event been already processed)
            if await self.idempotency_service.is_event_processed(event_id=event.event_id,
                                                                event_type=event.event_type):
                self.logger.info(f"Skipping duplicate inventory release for order: {event.order_id}")
                return

            self.logger.info(f"Processing inventory release for order {event.order_id}:{event.reason}")
            # Get product service with database session
            async for product_service in self._get_product_service():
                # Release inventory (restore quantities)
                await product_service.release_inventory(event.items)
                # marking event as processed
                await self.idempotency_service.mark_event_as_processed(event_id=event.event_id,
                                                                       event_type=event.event_type,
                                                                       order_id=event.order_id,
                                                                       result="released")
                self.logger.info(f"Successfully released inventory for order: {event.order_id}")

        except ProductReleaseError as error:
            self.logger.error(f"Error handling inventory release request for order: {event.order_id}: {str(error)}")
            # Note: We don't re-raise here because inventory release is a compensation
            # action and should be idempotent. We log the error but don't fail the message.


product_event_consumer = ProductEventConsumer(logger=logger)
