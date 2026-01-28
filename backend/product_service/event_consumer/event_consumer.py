from logging import Logger
from typing import Any

from database_layer.product_image_repository import ProductImageRepository
from database_layer.product_repository import ProductRepository
from service_layer.product_service import ProductService
from service_layer.product_image_service import ProductImageService
from shared.schemas.event_schemas import InventoryReserveRequested
from shared.shared_instances import logger, product_service_database_session_manager


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
    def __init__(self) -> None:
        self.logger: Logger = logger
        

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
        2. Check if all products are available in sufficient quantities
        3. If yes: Reserve inventory and publish InventoryReserveSucceeded
        4. If no: Publish InventoryReserveFailed with details
        
        Business Rules:
        - All items must be available, otherwise the entire reservation fails (atomicity)
        - Products must be in stock (in_stock=True)
        - Quantity must be sufficient for each item
        """
        try:
            # Parse the event
            event = InventoryReserveRequested(**message)
            self.logger.info(
                f"Processing inventory reservation for order {event.order_id} "
                f"with {len(event.items)} items"
            )
            
            # getting product service with db session
            async for product_service in self._get_product_service():
                # validating for sufficient quantity
                validation_result = await product_service._validate_inventory_availability(
                    product_service,
                    event.items
                )
                
                if not validation_result["success"]:
                    