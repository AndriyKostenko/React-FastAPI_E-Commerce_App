"""Resources owned exclusively by the user-service outbox executable."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from logging import Logger

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange

from events_publisher.user_events_publisher import UserEventPublisher
from resources import logger, settings
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings


@dataclass(slots=True)
class UserOutboxResources:
    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    broker: RabbitBroker
    exchange: RabbitExchange
    publisher: UserEventPublisher


def create_user_outbox_resources(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> UserOutboxResources:
    database = DatabaseSessionManager(
        database_url=app_settings.USER_SERVICE_DATABASE_URL,
        logger=app_logger,
        echo=app_settings.DEBUG_MODE,
        pg_max_connections=app_settings.PG_MAX_CONNECTIONS,
        reserved_connections=app_settings.PG_RESERVED_CONNECTIONS,
        num_db_services=app_settings.PG_DB_SERVICES_COUNT,
    )
    broker = RabbitBroker(url=app_settings.RABBITMQ_BROKER_URL)
    exchange = RabbitExchange(
        name="user.events.exchange",
        durable=True,
        type=ExchangeType.TOPIC,
    )
    publisher = UserEventPublisher(
        rabbitmq_broker=broker,
        exchange=exchange,
        logger=app_logger,
        settings=app_settings,
    )
    return UserOutboxResources(
        settings=app_settings,
        logger=app_logger,
        database=database,
        broker=broker,
        exchange=exchange,
        publisher=publisher,
    )


@asynccontextmanager
async def user_outbox_runtime(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> AsyncIterator[UserOutboxResources]:
    resources = create_user_outbox_resources(app_settings, app_logger)
    try:
        await resources.publisher.start()
        yield resources
    finally:
        try:
            await resources.publisher.stop()
        finally:
            await resources.database.close()
