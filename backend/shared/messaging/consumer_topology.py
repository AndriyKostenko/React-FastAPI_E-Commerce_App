"""Declares the dead-letter and retry topology behind a consumer's queues."""

from collections.abc import Awaitable, Callable
from logging import Logger

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange
from faststream.rabbit.message import RabbitMessage

from shared.messaging.resilient_queue import (
    DEAD_LETTER_EXCHANGE_NAME,
    ResilientQueue,
    RetrySchedule,
)
from shared.messaging.retry_dispatcher import RetryDispatcher


DEAD_LETTER_EXCHANGE = RabbitExchange(
    name=DEAD_LETTER_EXCHANGE_NAME,
    durable=True,
    type=ExchangeType.DIRECT,
)


class ConsumerTopology:
    """
    The queues one consumer process owns, and the machinery that keeps their
    failed messages.

    Every queue has always named ``dlx`` as its dead-letter exchange, but
    nothing ever declared it — RabbitMQ drops a message dead-lettered to an
    exchange that does not exist, so every handler failure was silently lost.
    ``declare()`` creates that exchange, each queue's DLQ bound to it, and the
    retry queues, and must run before the broker starts consuming.

    Usage in a consumer's ``app.py``::

        topology = ConsumerTopology(broker, logger)
        orders = topology.queue("orders", routing_key="order.*", dead_letter_key="orders.dlq")

        @app.on_startup
        async def startup():
            await topology.declare()

        @broker.subscriber(queue=orders.queue, exchange=order_exchange)
        async def handle(body: dict[str, object], message: RabbitMessage):
            await topology.dispatch(orders, message, lambda: consumer.handle(body))
    """

    def __init__(
        self,
        broker: RabbitBroker,
        logger: Logger,
        retry_schedule: RetrySchedule | None = None,
    ) -> None:
        self._broker = broker
        self._logger = logger
        self._retry_schedule = retry_schedule or RetrySchedule()
        self._dispatcher = RetryDispatcher(broker, logger)
        self._queues: dict[str, ResilientQueue] = {}

    @property
    def queues(self) -> tuple[ResilientQueue, ...]:
        return tuple(self._queues.values())

    def queue(
        self,
        name: str,
        routing_key: str,
        dead_letter_key: str,
        retry_schedule: RetrySchedule | None = None,
    ) -> ResilientQueue:
        """Define and register a consumer queue; call at module level, before subscribing."""
        if name in self._queues:
            raise ValueError(f"Queue {name!r} is already registered")
        resilient_queue = ResilientQueue(
            name=name,
            routing_key=routing_key,
            dead_letter_key=dead_letter_key,
            retry_schedule=retry_schedule or self._retry_schedule,
        )
        self._queues[name] = resilient_queue
        return resilient_queue

    async def declare(self) -> None:
        """Create the dead-letter exchange, every DLQ and every retry queue. Idempotent."""
        # connect() is a no-op once connected, and broker.start() reuses this
        # connection — so the topology exists before the first message is consumed.
        await self._broker.connect()
        dead_letter_exchange = await self._broker.declare_exchange(DEAD_LETTER_EXCHANGE)
        for resilient_queue in self._queues.values():
            dead_letter_queue = await self._broker.declare_queue(resilient_queue.dead_letter_queue)
            await dead_letter_queue.bind(
                dead_letter_exchange, routing_key=resilient_queue.dead_letter_key
            )
            for retry_queue in resilient_queue.retry_queues:
                await self._broker.declare_queue(retry_queue)
        self._logger.info(
            "Declared dead-letter and retry topology for %s queue(s)", len(self._queues)
        )

    async def dispatch(
        self,
        queue: ResilientQueue,
        message: RabbitMessage,
        handle: Callable[[], Awaitable[None]],
    ) -> None:
        """Run ``handle`` for a message from ``queue``, retrying or dead-lettering on failure."""
        await self._dispatcher.dispatch(queue, message, handle)
