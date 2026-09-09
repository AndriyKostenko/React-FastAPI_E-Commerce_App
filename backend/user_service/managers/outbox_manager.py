"""User-service outbox-relay resource ownership.

The relay is a separate process from the API and needs a much smaller graph:
a database to poll and a broker to publish to.  It follows the same
build-then-own shape as ``managers.resources_manager``.
"""

from contextlib import AsyncExitStack
from dataclasses import dataclass
from logging import Logger
from types import TracebackType
from typing import Final

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange

from events_publisher.user_events_publisher import UserEventPublisher
from managers.resources_manager import build_database, logger, settings
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings


@dataclass(slots=True)
class UserOutboxResources:
    """Everything the user-service outbox relay process needs."""

    settings: Settings
    logger: Logger
    database: DatabaseSessionManager
    broker: RabbitBroker
    exchange: RabbitExchange
    publisher: UserEventPublisher


class OutboxManager:
    """Builds and owns the resources of one user-service outbox process.

    The class itself satisfies ``shared.outbox``'s ``RuntimeFactory``: calling
    it yields an async context manager whose entered value is the container.
    """

    EXCHANGE_NAME: Final[str] = "user.events.exchange"

    def __init__(self, app_settings: Settings = settings, app_logger: Logger = logger) -> None:
        self.settings = app_settings
        self.logger = app_logger
        self._stack: AsyncExitStack | None = None

    def build(self) -> UserOutboxResources:
        """Assemble the outbox resource graph without connecting to anything."""
        broker = RabbitBroker(url=self.settings.RABBITMQ_BROKER_URL)
        exchange = RabbitExchange(
            name=self.EXCHANGE_NAME,
            durable=True,
            type=ExchangeType.TOPIC,
        )
        return UserOutboxResources(
            settings=self.settings,
            logger=self.logger,
            database=build_database(self.settings, self.logger),
            broker=broker,
            exchange=exchange,
            publisher=UserEventPublisher(
                rabbitmq_broker=broker,
                exchange=exchange,
                logger=self.logger,
                settings=self.settings,
            ),
        )

    async def __aenter__(self) -> UserOutboxResources:
        if self._stack is not None:
            raise RuntimeError(f"{type(self).__name__} is already open")
        resources = self.build()
        stack = AsyncExitStack()
        await stack.__aenter__()
        self._stack = stack
        try:
            # Starting the publisher opens the broker connection; the database
            # is registered first so it is the last thing closed on the way out.
            stack.push_async_callback(resources.database.close)
            await resources.publisher.start()
            stack.push_async_callback(resources.publisher.stop)
        except BaseException:
            self._stack = None
            await stack.aclose()
            raise
        return resources

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        stack, self._stack = self._stack, None
        if stack is not None:
            await stack.__aexit__(exc_type, exc_value, traceback)
