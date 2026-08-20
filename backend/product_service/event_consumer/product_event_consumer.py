from logging import Logger
from typing import Any

from database_layer.product_image_repository import ProductImageRepository
from database_layer.product_repository import ProductRepository
from database_layer.product_variant_repository import ProductVariantRepository
from database_layer.category_repository import CategoryRepository
from database_layer.supplier_import_repository import SupplierImportBatchRepository
from exceptions.product_exceptions import ProductCreationError, ProductReleaseError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from models.outbox_models import OutboxEvent
from models.supplier_import_models import SupplierImportBatch
from service_layer.product_service import ProductService
from service_layer.product_image_service import ProductImageService
from service_layer.category_service import CategoryService
from shared.database_layer.outbox_repository import OutboxRepository
from shared.contracts.events import (
    InventoryReserveRequested,
    InventoryReleaseRequested,
    SupplierProductsFetchedEvent,
    SupplierProductImportCompletedEvent,
)
from shared.managers.cache_manager import CacheManager
from shared.managers.database_session_manager import DatabaseSessionManager
from event_publisher.event_publisher import ProductEventPublisher
from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.enums.event_enums import InventoryEvents, SupplierEvents
from service_layer.supplier_product_mapper import SupplierProductMapper
from shared.settings import Settings

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
    """Consumer for product-related SAGA events, primarily inventory reservation and release requests from Order Service."""
    def __init__(
        self,
        logger: Logger,
        database: DatabaseSessionManager,
        idempotency_service: IdempotencyEventService,
        cache_manager: CacheManager,
        publisher: ProductEventPublisher,
        settings: Settings,
    ) -> None:
        self.logger: Logger = logger
        self.database = database
        self.idempotency_service = idempotency_service
        self.cache_manager = cache_manager
        self.publisher = publisher
        self.settings = settings

    async def _get_product_service(self):
        """
        Create a ProductService instance with a fresh database session.
        This mimics FastAPI's dependency injection but for FastStream consumers.
        """
        async with self.database.transaction() as session:
            product_image_service = ProductImageService(
                repository=ProductImageRepository(session=session)
            )
            product_service = ProductService(
                repository=ProductRepository(session=session),
                product_image_service=product_image_service,
                variant_repository=ProductVariantRepository(session=session),
                image_repository=ProductImageRepository(session=session),
                category_service=CategoryService(
                    CategoryRepository(session=session),
                    default_category_name=self.settings.CJ_DROPSHIPPING_DEFAULT_CATEGORY_NAME,
                ),
            )
            yield product_service

    async def handle_inventory_saga_event(self, message: dict[str, Any]):
        """
        Route inventory events to appropriate handlers based on event type
        """
        event_type = message.get("event_type")
        match event_type:
            case InventoryEvents.INVENTORY_RESERVE_REQUESTED:
                await self.handle_inventory_reserve_requested(message)
            case InventoryEvents.INVENTORY_RELEASE_REQUESTED:
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
            if not await self.idempotency_service.try_claim_event(event.event_id, event.event_type):
                self.logger.info(f"Skipping duplicate inventory reservation for order: {event.order_id}")
                return
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
                    await self.publisher.publish_inventory_reserve_failed(
                        order_id=event.order_id,
                        user_id=event.user_id,
                        user_email=event.user_email,
                        reasons=reserved_items["reasons"],
                        failed_items=reserved_items["failed_products"]
                    )
                    self.logger.warning(f"Inventory reservation failed for order: {str(event.order_id)} reasons: {reserved_items['reasons']}")
                    return

                # marking an event as processed
                await self.idempotency_service.mark_event_as_processed(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    order_id=event.order_id,
                    result="succeeded"
                )
                self.logger.info(f"Successfully reserved inventory for order: {event.order_id}")
                await self.cache_manager.invalidate_namespace(namespace="products")
                #5. publishing a success event to Order service
                await self.publisher.publish_inventory_reserve_succeeded(
                    order_id=event.order_id,
                    user_id=event.user_id,
                    user_email=event.user_email,
                    reserved_items=reserved_items["products"]
                )

        except Exception as error:
            # Release the idempotency claim so RabbitMQ retries are not blocked
            # by a stale "processing" marker left from this failed attempt.
            await self.idempotency_service.release_claim(event.event_id, event.event_type)
            # Critical error - log and publish failure event
            self.logger.error(f"Error handling inventory reserve request for order {event.order_id}: {str(error)}")
            await self.publisher.publish_inventory_reserve_failed(
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
            if not await self.idempotency_service.try_claim_event(event_id=event.event_id,
                                                                event_type=event.event_type):
                self.logger.info(f"Skipping duplicate inventory release for order: {event.order_id}")
                return

            self.logger.info(f"Processing inventory release for order {event.order_id}:{event.reason}")
            # Get product service with database session
            async for product_service in self._get_product_service():
                # Release inventory (restore quantities)
                await product_service.release_inventory(event.items)
                await self.cache_manager.invalidate_namespace(namespace="products")
                # marking event as processed
                await self.idempotency_service.mark_event_as_processed(event_id=event.event_id,
                                                                       event_type=event.event_type,
                                                                       order_id=event.order_id,
                                                                       result="released")
                self.logger.info(f"Successfully released inventory for order: {event.order_id}")

        except ProductReleaseError as error:
            self.logger.error(f"Error handling inventory release request for order: {event.order_id}: {str(error)}")
            # Release the claim so RabbitMQ retries are not blocked.
            # Note: We don't re-raise because inventory release is a compensation action;
            # logging and releasing the claim is sufficient to allow retry.
            await self.idempotency_service.release_claim(event.event_id, event.event_type)

    async def handle_supplier_products_fetched(self, message: dict[str, Any]):
        """Handle supplier product import events from supplier_service.

        Steps:
        1. Parse the event
        2. Check idempotency
        3. Map generic supplier products to CreateProduct DTOs
        4. Persist via bulk_upsert_products
        5. Persist import completed/failed feedback in the transactional outbox
        6. Invalidate product cache
        """
        event = SupplierProductsFetchedEvent(**message)
        try:
            self.logger.info(f"Processing supplier products fetched event for supplier: {event.supplier_id}, fetch_id: {event.fetch_id}, products: {len(event.products)}")
            async with self.database.transaction() as session:
                inbox_repository = SupplierImportBatchRepository(session)
                if await inbox_repository.get_by_event_id(event.event_id):
                    self.logger.info(
                        f"Skipping durable duplicate supplier import event {event.event_id}"
                    )
                    return

                inbox = await inbox_repository.create(
                    SupplierImportBatch(
                        event_id=event.event_id,
                        supplier_id=event.supplier_id,
                        fetch_id=event.fetch_id,
                        batch_id=event.batch_id,
                        batch_number=event.batch_number,
                        total_batches=event.total_batches,
                        imported=0,
                        updated=0,
                        failed=0,
                        errors=[],
                    )
                )

                product_repository = ProductRepository(session)
                image_repository = ProductImageRepository(session)
                category_service = CategoryService(
                    CategoryRepository(session),
                    default_category_name=self.settings.CJ_DROPSHIPPING_DEFAULT_CATEGORY_NAME,
                )
                product_service = ProductService(
                    repository=product_repository,
                    product_image_service=ProductImageService(image_repository),
                    variant_repository=ProductVariantRepository(session),
                    image_repository=image_repository,
                    category_service=category_service,
                )

                errors: list[str] = []
                for supplier_product in event.products:
                    pid = supplier_product.supplier_pid or "<missing>"
                    try:
                        local_category_id = await category_service.get_or_create_by_name(
                            supplier_product.category_name
                        )
                        product_data = SupplierProductMapper.map_supplier_product(
                            supplier_product,
                            local_category_id,
                        )
                        existing = await product_repository.get_by_supplier_pid(
                            supplier_product.supplier_id,
                            pid,
                        )
                        async with session.begin_nested():
                            await product_service.upsert_product_by_pid(product_data)
                        if existing:
                            inbox.updated += 1
                        else:
                            inbox.imported += 1
                    except (
                        ProductCreationError,
                        ValidationError,
                        IntegrityError,
                        ValueError,
                        ArithmeticError,
                    ) as product_error:
                        inbox.failed += 1
                        errors.append(f"{pid}: {product_error}")
                        self.logger.warning(
                            f"Rejected supplier product {pid} in batch {event.batch_id}: {product_error}"
                        )

                inbox.errors = errors[:100]
                await inbox_repository.update(inbox)

                completed_event = SupplierProductImportCompletedEvent(
                    supplier_id=event.supplier_id,
                    fetch_id=event.fetch_id,
                    batch_id=event.batch_id,
                    batch_number=event.batch_number,
                    total_batches=event.total_batches,
                    imported=inbox.imported,
                    updated=inbox.updated,
                    failed=inbox.failed,
                    errors=inbox.errors,
                )
                await OutboxRepository(session=session, model=OutboxEvent).create(
                    OutboxEvent(
                        event_type=completed_event.event_type,
                        payload=completed_event.model_dump(mode="json"),
                    )
                )

            try:
                await self.cache_manager.invalidate_namespace(namespace="products")
            except Exception:
                self.logger.exception(
                    "Supplier import committed but product cache invalidation failed"
                )
            self.logger.info(
                f"Supplier import batch committed for supplier {event.supplier_id}, "
                f"fetch_id {event.fetch_id}, batch {event.batch_number}/{event.total_batches}"
            )

        except Exception as error:
            self.logger.error(f"Error handling supplier products fetched event for supplier {event.supplier_id}, fetch_id {event.fetch_id}: {str(error)}")
            raise
