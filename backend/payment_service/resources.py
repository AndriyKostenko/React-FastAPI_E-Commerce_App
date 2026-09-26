"""Lifecycle-owned resources for each payment-service process role."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from logging import Logger

from faststream.rabbit import RabbitBroker
from starlette.requests import HTTPConnection
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
        # The revealed key: Stripe stores a SecretStr as-is and sends its masked
        # repr ("**********") as the credential, so every call failed to authenticate.
        api_key=app_settings.STRIPE_API_KEY,
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


def get_payment_api_resources(connection: HTTPConnection) -> PaymentApiResources:
    """Resolve the current app's lifespan-owned resource container."""
    resources = getattr(connection.app.state, "resources", None)
    if not isinstance(resources, PaymentApiResources):
        raise RuntimeError("Payment API resources are not initialized")
    return resources


@dataclass(slots=True)
class PaymentOutboxResources:
    """Resources owned by one payment-service outbox process.

    The instance is its own async context manager: ``__aenter__`` starts the
    publisher (opening the broker connection) and ``__aexit__`` unwinds the
    publisher and the database engine in reverse order.
    """

    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    broker: RabbitBroker
    publisher: PaymentEventPublisher

    async def __aenter__(self) -> "PaymentOutboxResources":
        await self.publisher.start()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        try:
            await self.publisher.stop()
        finally:
            await self.database.close()


def payment_outbox_resources(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> PaymentOutboxResources:
    """Build the resource graph for one payment-service outbox process."""
    broker = create_rabbitmq_broker(app_settings)
    return PaymentOutboxResources(
        settings=app_settings,
        logger=app_logger,
        database=create_database_session_manager(app_settings, app_logger),
        broker=broker,
        publisher=PaymentEventPublisher(
            rabbitmq_broker=broker,
            logger=app_logger,
            settings=app_settings,
        ),
    )


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
