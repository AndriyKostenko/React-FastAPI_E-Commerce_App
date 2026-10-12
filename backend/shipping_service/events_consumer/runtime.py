from dataclasses import dataclass
from logging import Logger

from faststream.rabbit import RabbitBroker, RabbitExchange

from events_publisher.shipping_event_publisher import ShippingEventPublisher
from infrastructure.idempotency.idempotency_service import IdempotencyEventService
from infrastructure.managers.database_session_manager import DatabaseSessionManager
from settings import Settings

from service_config import logger, settings


@dataclass(slots=True)
class ShippingConsumerResources:
    """Resources owned exclusively by one shipping consumer process."""

    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    idempotency: IdempotencyEventService
    event_publisher: ShippingEventPublisher

    async def start(self) -> None:
        await self.idempotency.connect()

    async def close(self) -> None:
        try:
            await self.idempotency.close()
        finally:
            await self.database.close()


def create_shipping_consumer_resources(
    *,
    broker: RabbitBroker,
    shipping_exchange: RabbitExchange,
) -> ShippingConsumerResources:
    database = DatabaseSessionManager(
        database_url=settings.SHIPPING_SERVICE_DATABASE_URL,
        logger=logger,
        echo=settings.DEBUG_MODE,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
    )
    idempotency = IdempotencyEventService(
        service_prefix="shipping-service",
        logger=logger,
        redis_url=settings.SHIPPING_SERVICE_REDIS_URL,
        service_api_version=settings.SHIPPING_SERVICE_URL_API_VERSION,
        ttl_hours=settings.IDEMPOTENCY_EVENT_SERVICE_HOURS,
    )
    event_publisher = ShippingEventPublisher(
        broker=broker,
        exchange=shipping_exchange,
        logger=logger,
        settings=settings,
    )
    return ShippingConsumerResources(
        settings=settings,
        logger=logger,
        database=database,
        idempotency=idempotency,
        event_publisher=event_publisher,
    )
