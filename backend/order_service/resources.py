"""Lifecycle-owned resources for each order-service process role."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from logging import Logger

from fastapi import Request
from faststream.rabbit import RabbitBroker

from config import logger, settings
from events_publisher.order_event_publisher import OrderEventPublisher
from messaging import create_rabbitmq_broker
from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings


def create_database_session_manager(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> DatabaseSessionManager:
    return DatabaseSessionManager(
        database_url=app_settings.ORDER_SERVICE_DATABASE_URL,
        logger=app_logger,
        echo=app_settings.DEBUG_MODE,
        pg_max_connections=app_settings.PG_MAX_CONNECTIONS,
        reserved_connections=app_settings.PG_RESERVED_CONNECTIONS,
        num_db_services=app_settings.PG_DB_SERVICES_COUNT,
    )


def create_idempotency_service() -> IdempotencyEventService:
    return IdempotencyEventService(
        service_prefix="order-service",
        redis_url=settings.ORDER_SERVICE_REDIS_URL,
        logger=logger,
        service_api_version=settings.ORDER_SERVICE_URL_API_VERSION,
        ttl_hours=settings.IDEMPOTENCY_EVENT_SERVICE_HOURS,
    )


@dataclass(slots=True)
class OrderApiResources:
    settings: Settings
    logger: Logger
    database: DatabaseSessionManager


def create_order_api_resources(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> OrderApiResources:
    """Construct resources owned by one order-service ASGI process."""
    return OrderApiResources(
        settings=app_settings,
        logger=app_logger,
        database=create_database_session_manager(app_settings, app_logger),
    )


@asynccontextmanager
async def order_api_runtime(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> AsyncIterator[OrderApiResources]:
    """Start and reliably stop resources owned by one order API process."""
    resources = create_order_api_resources(app_settings, app_logger)
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(resources.database)
        yield resources


def get_order_api_resources(request: Request) -> OrderApiResources:
    """Resolve the current app's lifespan-owned resource container."""
    resources = getattr(request.app.state, "resources", None)
    if not isinstance(resources, OrderApiResources):
        raise RuntimeError("Order API resources are not initialized")
    return resources


@dataclass(slots=True)
class OrderOutboxResources:
    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    broker: RabbitBroker
    publisher: OrderEventPublisher

    async def start(self) -> None:
        await self.publisher.start()

    async def close(self) -> None:
        try:
            await self.publisher.stop()
        finally:
            await self.database.close()


def create_outbox_resources() -> OrderOutboxResources:
    broker = create_rabbitmq_broker(settings)
    return OrderOutboxResources(
        settings=settings,
        logger=logger,
        database=create_database_session_manager(),
        broker=broker,
        publisher=OrderEventPublisher(
            rabbitmq_broker=broker,
            logger=logger,
            settings=settings,
        ),
    )


@asynccontextmanager
async def order_outbox_resources() -> AsyncIterator[OrderOutboxResources]:
    resources = create_outbox_resources()
    try:
        await resources.start()
        yield resources
    finally:
        await resources.close()


@dataclass(slots=True)
class OrderConsumerResources:
    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    idempotency: IdempotencyEventService
    publisher: OrderEventPublisher

    async def start(self) -> None:
        await self.idempotency.connect()

    async def close(self) -> None:
        try:
            await self.idempotency.close()
        finally:
            await self.database.close()


def create_consumer_resources(broker: RabbitBroker) -> OrderConsumerResources:
    return OrderConsumerResources(
        settings=settings,
        logger=logger,
        database=create_database_session_manager(),
        idempotency=create_idempotency_service(),
        publisher=OrderEventPublisher(
            rabbitmq_broker=broker,
            logger=logger,
            settings=settings,
        ),
    )
