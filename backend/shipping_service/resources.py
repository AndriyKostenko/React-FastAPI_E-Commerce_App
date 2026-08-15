from dataclasses import dataclass
from logging import Logger

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange

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


def create_shipping_api_resources() -> ShippingApiResources:
    """Build a fresh resource graph for one FastAPI lifespan."""
    database = DatabaseSessionManager(
        database_url=settings.SHIPPING_SERVICE_DATABASE_URL,
        logger=logger,
        echo=settings.DEBUG_MODE,
        pg_max_connections=settings.PG_MAX_CONNECTIONS,
        reserved_connections=settings.PG_RESERVED_CONNECTIONS,
        num_db_services=settings.PG_DB_SERVICES_COUNT,
    )
    broker = RabbitBroker(url=settings.RABBITMQ_BROKER_URL)
    exchange = RabbitExchange(
        name="shipping.events.exchange",
        durable=True,
        type=ExchangeType.TOPIC,
    )
    event_publisher = ShippingEventPublisher(
        broker=broker,
        exchange=exchange,
        logger=logger,
        settings=settings,
    )
    return ShippingApiResources(
        settings=settings,
        logger=logger,
        database=database,
        event_publisher=event_publisher,
    )
