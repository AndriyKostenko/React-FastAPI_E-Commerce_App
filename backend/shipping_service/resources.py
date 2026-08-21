from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from logging import Logger

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange
from starlette.requests import HTTPConnection

from events_publisher.shipping_event_publisher import ShippingEventPublisher
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings

from service_config import logger, settings


@dataclass(slots=True)
class ShippingApiResources:
    """Long-lived resources owned by one shipping API process."""

    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    event_publisher: ShippingEventPublisher


def create_shipping_api_resources(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> ShippingApiResources:
    """Build a fresh resource graph for one FastAPI lifespan."""
    database = DatabaseSessionManager(
        database_url=app_settings.SHIPPING_SERVICE_DATABASE_URL,
        logger=app_logger,
        echo=app_settings.DEBUG_MODE,
        pg_max_connections=app_settings.PG_MAX_CONNECTIONS,
        reserved_connections=app_settings.PG_RESERVED_CONNECTIONS,
        num_db_services=app_settings.PG_DB_SERVICES_COUNT,
    )
    broker = RabbitBroker(url=app_settings.RABBITMQ_BROKER_URL)
    exchange = RabbitExchange(
        name="shipping.events.exchange",
        durable=True,
        type=ExchangeType.TOPIC,
    )
    event_publisher = ShippingEventPublisher(
        broker=broker,
        exchange=exchange,
        logger=app_logger,
        settings=app_settings,
    )
    return ShippingApiResources(
        settings=app_settings,
        logger=app_logger,
        database=database,
        event_publisher=event_publisher,
    )


@asynccontextmanager
async def shipping_api_runtime(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> AsyncIterator[ShippingApiResources]:
    """Start and reliably stop resources owned by one shipping API process."""
    resources = create_shipping_api_resources(app_settings, app_logger)
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(resources.database)
        await stack.enter_async_context(resources.event_publisher)
        yield resources


def get_shipping_api_resources(connection: HTTPConnection) -> ShippingApiResources:
    """Resolve the current app's lifespan-owned resource container."""
    resources = getattr(connection.app.state, "resources", None)
    if not isinstance(resources, ShippingApiResources):
        raise RuntimeError("Shipping API resources are not initialized")
    return resources


@dataclass(slots=True)
class ShippingOutboxResources:
    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    event_publisher: ShippingEventPublisher


@asynccontextmanager
async def shipping_outbox_runtime() -> AsyncIterator[ShippingOutboxResources]:
    api_resources = create_shipping_api_resources(settings, logger)
    resources = ShippingOutboxResources(
        settings=settings,
        logger=logger,
        database=api_resources.database,
        event_publisher=api_resources.event_publisher,
    )
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(resources.database)
        await stack.enter_async_context(resources.event_publisher)
        yield resources
