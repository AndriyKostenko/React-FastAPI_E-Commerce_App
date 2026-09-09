"""Process-local resources owned by supplier-service entrypoints."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from logging import Logger

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange
from starlette.requests import HTTPConnection

from event_publisher.supplier_event_publisher import SupplierEventPublisher
from service_layer.cj_api_client import CJDropshippingAPIClient
from service_layer.cj_freight_service import FreightQuoteCache
from service_layer.product_service_client import ProductServiceClient
from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.managers.logger_manager import setup_logger
from shared.settings import Settings, get_settings


settings: Settings = get_settings()
logger: Logger = setup_logger("supplier-service")


def create_database_manager(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> DatabaseSessionManager:
    return DatabaseSessionManager(
        database_url=app_settings.SUPPLIER_SERVICE_DATABASE_URL,
        logger=app_logger,
        echo=app_settings.DEBUG_MODE,
        pg_max_connections=app_settings.PG_MAX_CONNECTIONS,
        reserved_connections=app_settings.PG_RESERVED_CONNECTIONS,
        num_db_services=app_settings.PG_DB_SERVICES_COUNT,
    )


@dataclass(slots=True)
class SupplierApiResources:
    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    cj_api_client: CJDropshippingAPIClient
    product_service_client: ProductServiceClient
    # One cache per ASGI process: checkout quotes are read far more often than
    # they change, and a shared cache would add a hop to the checkout path.
    freight_cache: FreightQuoteCache


@asynccontextmanager
async def supplier_api_runtime(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> AsyncIterator[SupplierApiResources]:
    """Start and reliably stop resources owned by one supplier API process."""
    resources = create_supplier_api_resources(app_settings, app_logger)
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(resources.database)
        await stack.enter_async_context(resources.cj_api_client)
        stack.push_async_callback(resources.product_service_client.close)
        await resources.product_service_client.start()
        yield resources


def create_supplier_api_resources(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> SupplierApiResources:
    """Construct resources owned by one supplier-service ASGI process."""
    return SupplierApiResources(
        settings=app_settings,
        logger=app_logger,
        database=create_database_manager(app_settings, app_logger),
        cj_api_client=CJDropshippingAPIClient(app_settings),
        product_service_client=ProductServiceClient(app_settings),
        freight_cache=FreightQuoteCache(
            ttl_seconds=app_settings.CJ_DROPSHIPPING_FREIGHT_CACHE_TTL_SECONDS,
            max_entries=app_settings.CJ_DROPSHIPPING_FREIGHT_CACHE_MAX_ENTRIES,
        ),
    )


def get_supplier_api_resources(connection: HTTPConnection) -> SupplierApiResources:
    """Resolve the current app's lifespan-owned resource container."""
    resources = getattr(connection.app.state, "resources", None)
    if not isinstance(resources, SupplierApiResources):
        raise RuntimeError("Supplier API resources are not initialized")
    return resources


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
    """Resources owned by one supplier-service outbox relay process.

    The instance is its own async context manager: ``__aenter__`` starts the
    publisher (opening the broker connection) and ``__aexit__`` unwinds the
    publisher and the database engine in reverse order.
    """

    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    broker: RabbitBroker
    publisher: SupplierEventPublisher

    async def __aenter__(self) -> "SupplierOutboxResources":
        await self.publisher.start()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        try:
            await self.publisher.stop()
        finally:
            await self.database.close()


def supplier_outbox_resources(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> SupplierOutboxResources:
    """Build the resource graph for one supplier-service outbox process."""
    broker = RabbitBroker(url=app_settings.RABBITMQ_BROKER_URL)
    supplier_exchange = RabbitExchange(
        name="supplier.events.exchange", durable=True, type=ExchangeType.TOPIC
    )
    order_exchange = RabbitExchange(
        name="order.events.exchange", durable=True, type=ExchangeType.TOPIC
    )
    inventory_exchange = RabbitExchange(
        name="inventory.events.exchange", durable=True, type=ExchangeType.TOPIC
    )
    return SupplierOutboxResources(
        settings=app_settings,
        logger=app_logger,
        database=create_database_manager(app_settings, app_logger),
        broker=broker,
        publisher=SupplierEventPublisher(
            broker=broker,
            supplier_exchange=supplier_exchange,
            order_exchange=order_exchange,
            inventory_exchange=inventory_exchange,
            logger=app_logger,
            settings=app_settings,
        ),
    )
