from dataclasses import dataclass
from logging import Logger

from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings

from service_config import logger, settings


@dataclass(slots=True)
class WishlistConsumerResources:
    """Resources owned exclusively by one wishlist consumer process."""

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


def create_wishlist_consumer_resources() -> WishlistConsumerResources:
    database = DatabaseSessionManager(
        database_url=settings.WISHLIST_SERVICE_DATABASE_URL,
        logger=logger,
        echo=settings.DEBUG_MODE,
        pg_max_connections=settings.PG_MAX_CONNECTIONS,
        reserved_connections=settings.PG_RESERVED_CONNECTIONS,
        num_db_services=settings.PG_DB_SERVICES_COUNT,
    )
    idempotency = IdempotencyEventService(
        service_prefix="wishlist-service",
        logger=logger,
        redis_url=settings.WISHLIST_SERVICE_REDIS_URL,
        service_api_version=settings.WISHLIST_SERVICE_URL_API_VERSION,
        ttl_hours=settings.IDEMPOTENCY_EVENT_SERVICE_HOURS,
    )
    return WishlistConsumerResources(
        settings=settings,
        logger=logger,
        database=database,
        idempotency=idempotency,
    )
