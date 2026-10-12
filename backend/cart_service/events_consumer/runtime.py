from dataclasses import dataclass
from logging import Logger

from infrastructure.idempotency.idempotency_service import IdempotencyEventService
from infrastructure.managers.database_session_manager import DatabaseSessionManager
from settings import Settings

from service_config import logger, settings


@dataclass(slots=True)
class CartConsumerResources:
    """Resources owned exclusively by one cart event-consumer process."""

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


def create_cart_consumer_resources() -> CartConsumerResources:
    database = DatabaseSessionManager(
        database_url=settings.CART_SERVICE_DATABASE_URL,
        logger=logger,
        echo=settings.DEBUG_MODE,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
    )
    idempotency = IdempotencyEventService(
        service_prefix="cart-service",
        logger=logger,
        redis_url=settings.CART_SERVICE_REDIS_URL,
        service_api_version=settings.CART_SERVICE_URL_API_VERSION,
        ttl_hours=settings.IDEMPOTENCY_EVENT_SERVICE_HOURS,
    )
    return CartConsumerResources(
        settings=settings,
        logger=logger,
        database=database,
        idempotency=idempotency,
    )
