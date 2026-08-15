"""Lifecycle-owned resources for each payment-service process role."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from logging import Logger

from faststream.rabbit import RabbitBroker

from config import logger, settings
from events_publisher.payment_event_publisher import PaymentEventPublisher
from messaging import create_rabbitmq_broker
from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings


def create_database_session_manager() -> DatabaseSessionManager:
    return DatabaseSessionManager(
        database_url=settings.PAYMENT_SERVICE_DATABASE_URL,
        logger=logger,
        echo=settings.DEBUG_MODE,
        pg_max_connections=settings.PG_MAX_CONNECTIONS,
        reserved_connections=settings.PG_RESERVED_CONNECTIONS,
        num_db_services=settings.PG_DB_SERVICES_COUNT,
    )


def create_idempotency_service() -> IdempotencyEventService:
    return IdempotencyEventService(
        service_prefix="payment-service",
        redis_url=settings.PAYMENT_SERVICE_REDIS_URL,
        logger=logger,
        service_api_version=settings.PAYMENT_SERVICE_URL_API_VERSION,
        ttl_hours=settings.IDEMPOTENCY_EVENT_SERVICE_HOURS,
    )


@dataclass(slots=True)
class PaymentApiResources:
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


def create_api_resources() -> PaymentApiResources:
    return PaymentApiResources(
        settings=settings,
        logger=logger,
        database=create_database_session_manager(),
        idempotency=create_idempotency_service(),
    )


@asynccontextmanager
async def payment_api_resources() -> AsyncIterator[PaymentApiResources]:
    resources = create_api_resources()
    try:
        await resources.start()
        yield resources
    finally:
        await resources.close()


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

    async def start(self) -> None:
        await self.idempotency.connect()

    async def close(self) -> None:
        try:
            await self.idempotency.close()
        finally:
            await self.database.close()


def create_consumer_resources() -> PaymentConsumerResources:
    return PaymentConsumerResources(
        settings=settings,
        logger=logger,
        database=create_database_session_manager(),
        idempotency=create_idempotency_service(),
    )
