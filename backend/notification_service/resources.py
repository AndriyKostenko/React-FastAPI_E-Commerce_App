"""Process-local resources owned by notification-service entrypoints."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from logging import Logger

from fastapi import Request
from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.managers.logger_manager import setup_logger
from shared.settings import Settings, get_settings


settings: Settings = get_settings()
logger: Logger = setup_logger("notification-service")


def create_database_manager(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> DatabaseSessionManager:
    return DatabaseSessionManager(
        database_url=app_settings.NOTIFICATION_SERVICE_DATABASE_URL,
        logger=app_logger,
        echo=app_settings.DEBUG_MODE,
        pg_max_connections=app_settings.PG_MAX_CONNECTIONS,
        reserved_connections=app_settings.PG_RESERVED_CONNECTIONS,
        num_db_services=app_settings.PG_DB_SERVICES_COUNT,
    )


@dataclass(slots=True)
class NotificationApiResources:
    settings: Settings
    logger: Logger
    database: DatabaseSessionManager


@asynccontextmanager
async def notification_api_runtime(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> AsyncIterator[NotificationApiResources]:
    """Start and reliably stop resources owned by one notification API process."""
    resources = create_notification_api_resources(app_settings, app_logger)
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(resources.database)
        yield resources


def create_notification_api_resources(
    app_settings: Settings = settings,
    app_logger: Logger = logger,
) -> NotificationApiResources:
    """Construct resources owned by one notification-service ASGI process."""
    return NotificationApiResources(
        settings=app_settings,
        logger=app_logger,
        database=create_database_manager(app_settings, app_logger),
    )


def get_notification_api_resources(request: Request) -> NotificationApiResources:
    """Resolve the current app's lifespan-owned resource container."""
    resources = getattr(request.app.state, "resources", None)
    if not isinstance(resources, NotificationApiResources):
        raise RuntimeError("Notification API resources are not initialized")
    return resources


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
