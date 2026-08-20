"""Process-local resources owned by product-service entrypoints."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from logging import Logger

from aiohttp import ClientSession
from fastapi import Request
from faststream.rabbit import RabbitBroker, RabbitExchange

from event_publisher.event_publisher import ProductEventPublisher
from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.managers.cache_manager import CacheManager
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.managers.logger_manager import setup_logger
from shared.settings import Settings, get_settings


settings: Settings = get_settings()
logger: Logger = setup_logger("product-service")


def create_database_manager(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> DatabaseSessionManager:
    return DatabaseSessionManager(
        database_url=app_settings.PRODUCT_SERVICE_DATABASE_URL,
        logger=app_logger,
        echo=app_settings.DEBUG_MODE,
        pg_max_connections=app_settings.PG_MAX_CONNECTIONS,
        reserved_connections=app_settings.PG_RESERVED_CONNECTIONS,
        num_db_services=app_settings.PG_DB_SERVICES_COUNT,
    )


def create_cache_manager(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> CacheManager:
    return CacheManager(
        service_prefix="product-service",
        redis_url=app_settings.PRODUCT_SERVICE_REDIS_URL,
        logger=app_logger,
        service_api_version=app_settings.PRODUCT_SERVICE_URL_API_VERSION,
    )


@dataclass(slots=True)
class ProductApiResources:
    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    cache: CacheManager
    http_session: ClientSession


@asynccontextmanager
async def product_api_runtime(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> AsyncIterator[ProductApiResources]:
    """Start and reliably stop resources owned by one product API process."""
    resources = create_product_api_resources(app_settings, app_logger)
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(resources.database)
        await stack.enter_async_context(resources.cache)
        await stack.enter_async_context(resources.http_session)
        yield resources


def create_product_api_resources(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> ProductApiResources:
    """Construct resources owned by one product-service ASGI process."""
    return ProductApiResources(
        settings=app_settings,
        logger=app_logger,
        database=create_database_manager(app_settings, app_logger),
        cache=create_cache_manager(app_settings, app_logger),
        http_session=ClientSession(),
    )


def get_product_api_resources(request: Request) -> ProductApiResources:
    """Resolve the current app's lifespan-owned resource container."""
    resources = getattr(request.app.state, "resources", None)
    if not isinstance(resources, ProductApiResources):
        raise RuntimeError("Product API resources are not initialized")
    return resources


@dataclass(slots=True)
class ProductConsumerResources:
    """Infrastructure owned by one product FastStream process."""

    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    idempotency: IdempotencyEventService
    cache: CacheManager
    publisher: ProductEventPublisher

    async def start(self) -> None:
        await self.idempotency.connect()
        try:
            await self.cache.connect()
        except Exception:
            await self.idempotency.close()
            raise

    async def close(self) -> None:
        try:
            await self.cache.close()
        finally:
            try:
                await self.idempotency.close()
            finally:
                await self.database.close()


def create_product_consumer_resources(
    *,
    broker: RabbitBroker,
    inventory_exchange: RabbitExchange,
    supplier_exchange: RabbitExchange,
) -> ProductConsumerResources:
    """Build a fresh resource graph for one product consumer process."""
    return ProductConsumerResources(
        settings=settings,
        logger=logger,
        database=create_database_manager(),
        idempotency=IdempotencyEventService(
            service_prefix="product-service",
            logger=logger,
            redis_url=settings.PRODUCT_SERVICE_REDIS_URL,
            service_api_version=settings.PRODUCT_SERVICE_URL_API_VERSION,
            ttl_hours=settings.IDEMPOTENCY_EVENT_SERVICE_HOURS,
        ),
        cache=CacheManager(
            service_prefix="api-gateway",
            redis_url=settings.APIGATEWAY_SERVICE_REDIS_URL,
            logger=logger,
            service_api_version=settings.API_GATEWAY_SERVICE_URL_API_VERSION,
        ),
        publisher=ProductEventPublisher(
            broker=broker,
            inventory_exchange=inventory_exchange,
            supplier_exchange=supplier_exchange,
            logger=logger,
            settings=settings,
        ),
    )


@dataclass(slots=True)
class ProductOutboxResources:
    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    publisher: ProductEventPublisher

    async def start(self) -> None:
        await self.publisher.start()

    async def close(self) -> None:
        try:
            await self.publisher.stop()
        finally:
            await self.database.close()


@asynccontextmanager
async def product_outbox_resources(
    *,
    broker: RabbitBroker,
    inventory_exchange: RabbitExchange,
    supplier_exchange: RabbitExchange,
) -> AsyncIterator[ProductOutboxResources]:
    resources = ProductOutboxResources(
        settings=settings,
        logger=logger,
        database=create_database_manager(),
        publisher=ProductEventPublisher(
            broker=broker,
            inventory_exchange=inventory_exchange,
            supplier_exchange=supplier_exchange,
            logger=logger,
            settings=settings,
        ),
    )
    try:
        await resources.start()
        yield resources
    finally:
        await resources.close()
