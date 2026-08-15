"""Process-local resources owned by product-service entrypoints."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from logging import Logger

from aiohttp import ClientSession
from faststream.rabbit import RabbitBroker, RabbitExchange

from event_publisher.event_publisher import ProductEventPublisher
from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.managers.cache_manager import CacheManager
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.managers.logger_manager import setup_logger
from shared.settings import Settings, get_settings


settings: Settings = get_settings()
logger: Logger = setup_logger("product-service")


def create_database_manager() -> DatabaseSessionManager:
    return DatabaseSessionManager(
        database_url=settings.PRODUCT_SERVICE_DATABASE_URL,
        logger=logger,
        echo=settings.DEBUG_MODE,
        pg_max_connections=settings.PG_MAX_CONNECTIONS,
        reserved_connections=settings.PG_RESERVED_CONNECTIONS,
        num_db_services=settings.PG_DB_SERVICES_COUNT,
    )


def create_cache_manager() -> CacheManager:
    return CacheManager(
        service_prefix="product-service",
        redis_url=settings.PRODUCT_SERVICE_REDIS_URL,
        logger=logger,
        service_api_version=settings.PRODUCT_SERVICE_URL_API_VERSION,
    )


@dataclass(slots=True)
class ProductApiResources:
    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    cache: CacheManager
    http_session: ClientSession


@asynccontextmanager
async def product_api_resources() -> AsyncIterator[ProductApiResources]:
    """Create and close resources used by one product API process."""
    database = create_database_manager()
    cache = create_cache_manager()
    http_session = ClientSession()
    try:
        await cache.connect()
        yield ProductApiResources(
            settings=settings,
            logger=logger,
            database=database,
            cache=cache,
            http_session=http_session,
        )
    finally:
        try:
            await http_session.close()
        finally:
            try:
                await cache.close()
            finally:
                await database.close()


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
