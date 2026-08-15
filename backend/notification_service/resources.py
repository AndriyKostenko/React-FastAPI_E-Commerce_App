"""Process-local resources owned by notification-service entrypoints."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from logging import Logger

from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.managers.logger_manager import setup_logger
from shared.settings import Settings, get_settings


settings: Settings = get_settings()
logger: Logger = setup_logger("notification-service")


def create_database_manager() -> DatabaseSessionManager:
    return DatabaseSessionManager(
        database_url=settings.NOTIFICATION_SERVICE_DATABASE_URL,
        logger=logger,
        echo=settings.DEBUG_MODE,
        pg_max_connections=settings.PG_MAX_CONNECTIONS,
        reserved_connections=settings.PG_RESERVED_CONNECTIONS,
        num_db_services=settings.PG_DB_SERVICES_COUNT,
    )


@dataclass(slots=True)
class NotificationApiResources:
    settings: Settings
    logger: Logger
    database: DatabaseSessionManager


@asynccontextmanager
async def notification_api_resources() -> AsyncIterator[NotificationApiResources]:
    """Create and close resources used by one notification API process."""
    database = create_database_manager()
    try:
        yield NotificationApiResources(
            settings=settings,
            logger=logger,
            database=database,
        )
    finally:
        await database.close()


@dataclass(slots=True)
class NotificationConsumerResources:
    """Infrastructure owned by one notification FastStream process."""

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


def create_notification_consumer_resources() -> NotificationConsumerResources:
    return NotificationConsumerResources(
        settings=settings,
        logger=logger,
        database=create_database_manager(),
        idempotency=IdempotencyEventService(
            service_prefix=settings.NOTIFICATION_SERVICE_REDIS_PREFIX,
            logger=logger,
            redis_url=settings.NOTIFICATION_SERVICE_REDIS_URL,
            service_api_version=settings.NOTIFICATION_SERVICE_URL_API_VERSION,
            ttl_hours=settings.IDEMPOTENCY_EVENT_SERVICE_HOURS,
        ),
    )
