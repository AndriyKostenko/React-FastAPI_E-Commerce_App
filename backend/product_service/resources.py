"""Process-local resources owned by product-service entrypoints."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from logging import Logger

from aiohttp import ClientSession
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange
from starlette.requests import HTTPConnection

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
        # Register the already-open HTTP client first so a failure while
        # starting the database or cache still closes its connector.
        await stack.enter_async_context(resources.http_session)
        await stack.enter_async_context(resources.database)
        await stack.enter_async_context(resources.cache)
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


def get_product_api_resources(connection: HTTPConnection) -> ProductApiResources:
    """Resolve the current app's lifespan-owned resource container."""
    resources = getattr(connection.app.state, "resources", None)
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
        cache=create_cache_manager(),
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
    """Resources owned by one product-service outbox process.

    The instance is its own async context manager: ``__aenter__`` starts the
    publisher (opening the broker connection) and ``__aexit__`` unwinds the
    publisher and the database engine in reverse order.
    """

    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    broker: RabbitBroker
    publisher: ProductEventPublisher

    async def __aenter__(self) -> "ProductOutboxResources":
        await self.publisher.start()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        try:
            await self.publisher.stop()
        finally:
            await self.database.close()


def product_outbox_resources(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> ProductOutboxResources:
    """Build the resource graph for one product-service outbox process."""
    broker = RabbitBroker(url=app_settings.RABBITMQ_BROKER_URL)
    inventory_exchange = RabbitExchange(
        name="inventory.events.exchange", durable=True, type=ExchangeType.TOPIC
    )
    supplier_exchange = RabbitExchange(
        name="supplier.events.exchange", durable=True, type=ExchangeType.TOPIC
    )
    return ProductOutboxResources(
        settings=app_settings,
        logger=app_logger,
        database=create_database_manager(app_settings, app_logger),
        broker=broker,
        publisher=ProductEventPublisher(
            broker=broker,
            inventory_exchange=inventory_exchange,
            supplier_exchange=supplier_exchange,
            logger=app_logger,
            settings=app_settings,
        ),
    )
