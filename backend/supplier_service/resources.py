"""Process-local resources owned by supplier-service entrypoints."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from logging import Logger

from faststream.rabbit import RabbitBroker, RabbitExchange

from event_publisher.supplier_event_publisher import SupplierEventPublisher
from service_layer.cj_api_client import CJDropshippingAPIClient
from service_layer.product_service_client import ProductServiceClient
from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.managers.logger_manager import setup_logger
from shared.settings import Settings, get_settings


settings: Settings = get_settings()
logger: Logger = setup_logger("supplier-service")


def create_database_manager() -> DatabaseSessionManager:
    return DatabaseSessionManager(
        database_url=settings.SUPPLIER_SERVICE_DATABASE_URL,
        logger=logger,
        echo=settings.DEBUG_MODE,
        pg_max_connections=settings.PG_MAX_CONNECTIONS,
        reserved_connections=settings.PG_RESERVED_CONNECTIONS,
        num_db_services=settings.PG_DB_SERVICES_COUNT,
    )


@dataclass(slots=True)
class SupplierApiResources:
    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    cj_api_client: CJDropshippingAPIClient


@asynccontextmanager
async def supplier_api_resources() -> AsyncIterator[SupplierApiResources]:
    """Create and close resources used by one supplier API process."""
    database = create_database_manager()
    cj_api_client = CJDropshippingAPIClient(settings)
    try:
        await cj_api_client.start()
        yield SupplierApiResources(
            settings=settings,
            logger=logger,
            database=database,
            cj_api_client=cj_api_client,
        )
    finally:
        try:
            await cj_api_client.close()
        finally:
            await database.close()


@dataclass(slots=True)
class SupplierConsumerResources:
    """Infrastructure owned by one supplier FastStream process."""

    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    idempotency: IdempotencyEventService
    cj_api_client: CJDropshippingAPIClient
    product_service_client: ProductServiceClient
    publisher: SupplierEventPublisher

    async def start(self) -> None:
        await self.idempotency.connect()
        try:
            await self.cj_api_client.start()
            await self.product_service_client.start()
        except Exception:
            await self.close()
            raise

    async def close(self) -> None:
        try:
            await self.product_service_client.close()
        finally:
            try:
                await self.cj_api_client.close()
            finally:
                try:
                    await self.idempotency.close()
                finally:
                    await self.database.close()


def create_supplier_consumer_resources(
    *,
    broker: RabbitBroker,
    supplier_exchange: RabbitExchange,
    order_exchange: RabbitExchange,
    inventory_exchange: RabbitExchange,
) -> SupplierConsumerResources:
    return SupplierConsumerResources(
        settings=settings,
        logger=logger,
        database=create_database_manager(),
        idempotency=IdempotencyEventService(
            service_prefix="supplier-service",
            logger=logger,
            redis_url=settings.SUPPLIER_SERVICE_REDIS_URL,
            service_api_version=settings.SUPPLIER_SERVICE_URL_API_VERSION,
            ttl_hours=settings.IDEMPOTENCY_EVENT_SERVICE_HOURS,
        ),
        cj_api_client=CJDropshippingAPIClient(settings),
        product_service_client=ProductServiceClient(settings),
        publisher=SupplierEventPublisher(
            broker=broker,
            supplier_exchange=supplier_exchange,
            order_exchange=order_exchange,
            inventory_exchange=inventory_exchange,
            logger=logger,
            settings=settings,
        ),
    )


@dataclass(slots=True)
class SupplierOutboxResources:
    """Infrastructure owned by one supplier outbox relay process."""

    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    broker: RabbitBroker
    publisher: SupplierEventPublisher

    async def start(self) -> None:
        await self.publisher.start()

    async def close(self) -> None:
        try:
            await self.publisher.stop()
        finally:
            await self.database.close()


def create_supplier_outbox_resources(
    *,
    broker: RabbitBroker,
    supplier_exchange: RabbitExchange,
    order_exchange: RabbitExchange,
    inventory_exchange: RabbitExchange,
) -> SupplierOutboxResources:
    return SupplierOutboxResources(
        settings=settings,
        logger=logger,
        database=create_database_manager(),
        broker=broker,
        publisher=SupplierEventPublisher(
            broker=broker,
            supplier_exchange=supplier_exchange,
            order_exchange=order_exchange,
            inventory_exchange=inventory_exchange,
            logger=logger,
            settings=settings,
        ),
    )


@asynccontextmanager
async def supplier_outbox_resources(
    *,
    broker: RabbitBroker,
    supplier_exchange: RabbitExchange,
    order_exchange: RabbitExchange,
    inventory_exchange: RabbitExchange,
) -> AsyncIterator[SupplierOutboxResources]:
    resources = create_supplier_outbox_resources(
        broker=broker,
        supplier_exchange=supplier_exchange,
        order_exchange=order_exchange,
        inventory_exchange=inventory_exchange,
    )
    try:
        await resources.start()
        yield resources
    finally:
        await resources.close()
