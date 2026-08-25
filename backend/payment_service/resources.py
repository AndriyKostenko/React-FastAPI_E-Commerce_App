"""Lifecycle-owned resources for each payment-service process role."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from logging import Logger

from fastapi import Request
from faststream.rabbit import RabbitBroker
from stripe import HTTPXClient, StripeClient

from config import logger, settings
from events_publisher.payment_event_publisher import PaymentEventPublisher
from messaging import create_rabbitmq_broker
from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings


def create_stripe_client(
    app_settings: Settings = settings,
) -> tuple[StripeClient, HTTPXClient]:
    """Create one process-owned async Stripe transport with bounded I/O."""
    http_client = HTTPXClient(timeout=app_settings.STRIPE_REQUEST_TIMEOUT_SECONDS)
    client = StripeClient(
        api_key=app_settings.STRIPE_TEST_SECRET_KEY,
        max_network_retries=app_settings.STRIPE_MAX_NETWORK_RETRIES,
        http_client=http_client,
    )
    return client, http_client


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
    stripe_client: StripeClient
    stripe_http_client: HTTPXClient


def create_payment_api_resources(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> PaymentApiResources:
    """Construct resources owned by one payment-service ASGI process."""
    stripe_client, stripe_http_client = create_stripe_client(app_settings)
    return PaymentApiResources(
        settings=app_settings,
        logger=app_logger,
        database=create_database_session_manager(app_settings, app_logger),
        idempotency=create_idempotency_service(app_settings, app_logger),
        stripe_client=stripe_client,
        stripe_http_client=stripe_http_client,
    )


@asynccontextmanager
async def payment_api_runtime(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> AsyncIterator[PaymentApiResources]:
    """Start and reliably stop resources owned by one payment API process."""
    resources = create_payment_api_resources(app_settings, app_logger)
    async with AsyncExitStack() as stack:
        stack.push_async_callback(resources.stripe_http_client.close_async)
        await stack.enter_async_context(resources.database)
        await stack.enter_async_context(resources.idempotency)
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
    stripe_client: StripeClient
    stripe_http_client: HTTPXClient

    async def start(self) -> None:
        await self.idempotency.connect()

    async def close(self) -> None:
        try:
            await self.stripe_http_client.close_async()
        finally:
            try:
                await self.idempotency.close()
            finally:
                await self.database.close()


def create_consumer_resources() -> PaymentConsumerResources:
    stripe_client, stripe_http_client = create_stripe_client()
    return PaymentConsumerResources(
        settings=settings,
        logger=logger,
        database=create_database_session_manager(),
        idempotency=create_idempotency_service(),
        stripe_client=stripe_client,
        stripe_http_client=stripe_http_client,
    )
