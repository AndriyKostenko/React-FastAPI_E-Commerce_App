"""Lifecycle-owned resources for each payment-service process role."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from logging import Logger

from fastapi import Request
from faststream.rabbit import RabbitBroker

from config import logger, settings
from events_publisher.payment_event_publisher import PaymentEventPublisher
from messaging import create_rabbitmq_broker
from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings


def create_database_session_manager(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> DatabaseSessionManager:
    return DatabaseSessionManager(
        database_url=app_settings.PAYMENT_SERVICE_DATABASE_URL,
        logger=app_logger,
        echo=app_settings.DEBUG_MODE,
        pg_max_connections=app_settings.PG_MAX_CONNECTIONS,
        reserved_connections=app_settings.PG_RESERVED_CONNECTIONS,
        num_db_services=app_settings.PG_DB_SERVICES_COUNT,
    )


def create_idempotency_service(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> IdempotencyEventService:
    return IdempotencyEventService(
        service_prefix="payment-service",
        redis_url=app_settings.PAYMENT_SERVICE_REDIS_URL,
        logger=app_logger,
        service_api_version=app_settings.PAYMENT_SERVICE_URL_API_VERSION,
        ttl_hours=app_settings.IDEMPOTENCY_EVENT_SERVICE_HOURS,
    )


@dataclass(slots=True)
class PaymentApiResources:
    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    idempotency: IdempotencyEventService


def create_payment_api_resources(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> PaymentApiResources:
    """Construct resources owned by one payment-service ASGI process."""
    return PaymentApiResources(
        settings=app_settings,
        logger=app_logger,
        database=create_database_session_manager(app_settings, app_logger),
        idempotency=create_idempotency_service(app_settings, app_logger),
    )


@asynccontextmanager
async def payment_api_runtime(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> AsyncIterator[PaymentApiResources]:
    """Start and reliably stop resources owned by one payment API process."""
    resources = create_payment_api_resources(app_settings, app_logger)
    async with AsyncExitStack() as stack:
        stack.push_async_callback(resources.database.close)
        stack.push_async_callback(resources.idempotency.close)
        await resources.idempotency.connect()
        yield resources


def get_payment_api_resources(request: Request) -> PaymentApiResources:
    """Resolve the current app's lifespan-owned resource container."""
    resources = getattr(request.app.state, "resources", None)
    if not isinstance(resources, PaymentApiResources):
        raise RuntimeError("Payment API resources are not initialized")
    return resources


@dataclass(slots=True)
class PaymentOutboxResources:
    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    broker: RabbitBroker
    publisher: PaymentEventPublisher

    async def start(self) -> None:
        await self.publisher.start()

    async def close(self) -> None:
        try:
            await self.publisher.stop()
        finally:
            await self.database.close()


def create_outbox_resources() -> PaymentOutboxResources:
    broker = create_rabbitmq_broker(settings)
    return PaymentOutboxResources(
        settings=settings,
        logger=logger,
        database=create_database_session_manager(),
        broker=broker,
        publisher=PaymentEventPublisher(
            rabbitmq_broker=broker,
            logger=logger,
            settings=settings,
        ),
    )


@asynccontextmanager
async def payment_outbox_resources() -> AsyncIterator[PaymentOutboxResources]:
    resources = create_outbox_resources()
    try:
        await resources.start()
        yield resources
    finally:
        await resources.close()


@dataclass(slots=True)
class PaymentConsumerResources:
    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    idempotency: IdempotencyEventService

    async def start(self) -> None:
        await self.idempotency.connect()

    async def close(self) -> None:
        try:
            await self.idempotency.close()
        finally:
            await self.database.close()


def create_consumer_resources() -> PaymentConsumerResources:
    return PaymentConsumerResources(
        settings=settings,
        logger=logger,
        database=create_database_session_manager(),
        idempotency=create_idempotency_service(),
    )
