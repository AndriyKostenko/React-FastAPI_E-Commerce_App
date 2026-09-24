"""
ConsumerTopology against a real RabbitMQ — no mocks: the point is to prove that
RabbitMQ itself routes a failed message through the retry queues and into the
DLQ, which only a live broker can show.

Needs the local broker (./local/dev.sh infra up). Queues get unique names and
are deleted afterwards.
"""

import asyncio
from collections.abc import AsyncGenerator
from logging import getLogger
from uuid import uuid4

import aio_pika
import pytest
from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange
from faststream.rabbit.annotations import RabbitMessage
from pydantic import BaseModel

from shared.messaging import (
    RETRY_ATTEMPT_HEADER,
    ConsumerTopology,
    PermanentMessageError,
    ResilientQueue,
    RetrySchedule,
)
from shared.settings import get_settings



FAST_RETRIES = RetrySchedule(delays_ms=(200, 400))
BROKER_URL = get_settings().RABBITMQ_BROKER_URL
EXCHANGE = RabbitExchange(
    name="test.consumer-topology.exchange", durable=False, auto_delete=True, type=ExchangeType.TOPIC
)


class OrderPayload(BaseModel):
    order_id: str


class HandlerProbe:
    """Records every delivery and fails the first ``failures`` of them."""

    def __init__(self, failures: int, error: Exception | None = None) -> None:
        self.failures = failures
        self.error = error or RuntimeError("transient failure")
        self.attempts: list[int] = []
        self.deliveries = 0  # counted before payload validation, unlike attempts
        self.succeeded = asyncio.Event()

    async def handle(self, message: RabbitMessage) -> None:
        self.attempts.append(int(message.headers.get(RETRY_ATTEMPT_HEADER, 0)))
        if len(self.attempts) <= self.failures:
            raise self.error
        self.succeeded.set()


@pytest.fixture
async def amqp() -> AsyncGenerator[aio_pika.abc.AbstractChannel, None]:
    connection = await aio_pika.connect_robust(BROKER_URL)
    channel = await connection.channel()
    yield channel
    await connection.close()


async def _drain(channel: aio_pika.abc.AbstractChannel, queue_name: str, timeout: float) -> list[bytes]:
    """Wait up to ``timeout`` for the first message on ``queue_name``, then take whatever is there."""
    queue = await channel.declare_queue(queue_name, passive=True)
    bodies: list[bytes] = []
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        incoming = await queue.get(fail=False)
        if incoming is not None:
            await incoming.ack()
            bodies.append(incoming.body)
        elif bodies:
            break
        else:
            await asyncio.sleep(0.05)
    return bodies


async def _delete_topology(channel: aio_pika.abc.AbstractChannel, queue: ResilientQueue) -> None:
    for name in (queue.name, queue.dead_letter_key, *(q.name for q in queue.retry_queues)):
        await channel.queue_delete(name)


async def _run(probe: HandlerProbe, payload: bytes, expected_deliveries: int) -> ResilientQueue:
    """Start a consumer wired through ConsumerTopology, publish one message, return its queue."""
    broker = RabbitBroker(BROKER_URL)
    topology = ConsumerTopology(broker, getLogger("test.consumer-topology"), FAST_RETRIES)
    suffix = uuid4().hex[:8]
    queue = topology.queue(
        name=f"test.topology.{suffix}", routing_key=f"test.{suffix}", dead_letter_key=f"test.topology.{suffix}.dlq"
    )

    @broker.subscriber(queue=queue.queue, exchange=EXCHANGE)
    async def handler(body: dict[str, str], message: RabbitMessage) -> None:
        probe.deliveries += 1

        async def handle() -> None:
            OrderPayload.model_validate(body)
            await probe.handle(message)

        await topology.dispatch(queue, message, handle)

    await topology.declare()
    await broker.start()
    try:
        await broker.publish(payload, exchange=EXCHANGE, routing_key=f"test.{suffix}", content_type="application/json")
        await asyncio.wait_for(_settled(probe, expected_deliveries), timeout=5)
    except BaseException:
        # The caller never receives the queue on failure, so it cannot clean up.
        await broker.stop()
        connection = await aio_pika.connect_robust(BROKER_URL)
        async with connection:
            await _delete_topology(await connection.channel(), queue)
        raise
    await broker.stop()
    return queue


async def _settled(probe: HandlerProbe, expected_deliveries: int) -> None:
    while not probe.succeeded.is_set() and probe.deliveries < expected_deliveries:
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.3)  # let the final reject reach the DLQ


async def test_transient_failure_is_retried_until_it_succeeds(amqp: aio_pika.abc.AbstractChannel) -> None:
    probe = HandlerProbe(failures=2)
    queue = await _run(probe, b'{"order_id": "o-1"}', expected_deliveries=3)
    try:
        assert probe.succeeded.is_set()
        # First delivery, then one delivery per retry, each carrying its counter.
        assert probe.attempts == [0, 1, 2]
        assert await _drain(amqp, queue.dead_letter_key, timeout=0.5) == []
    finally:
        await _delete_topology(amqp, queue)


async def test_exhausted_retries_park_the_message_in_the_dlq(amqp: aio_pika.abc.AbstractChannel) -> None:
    probe = HandlerProbe(failures=99)
    # One first delivery plus one per retry in the schedule.
    queue = await _run(probe, b'{"order_id": "o-2"}', expected_deliveries=FAST_RETRIES.max_retries + 1)
    try:
        assert not probe.succeeded.is_set()
        assert probe.attempts == [0, 1, 2]
        # The original body survives the round trip through both retry queues.
        assert await _drain(amqp, queue.dead_letter_key, timeout=2) == [b'{"order_id": "o-2"}']
    finally:
        await _delete_topology(amqp, queue)


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        (b'{"unexpected": "shape"}', None),  # pydantic ValidationError from the payload
        (b'{"order_id": "o-3"}', PermanentMessageError("order no longer exists")),
    ],
)
async def test_permanent_failure_skips_retries(
    amqp: aio_pika.abc.AbstractChannel, payload: bytes, error: Exception | None
) -> None:
    probe = HandlerProbe(failures=99, error=error)
    queue = await _run(probe, payload, expected_deliveries=1)
    try:
        # A malformed payload fails validation before the probe ever runs.
        assert probe.deliveries == 1
        assert probe.attempts == ([] if error is None else [0])
        assert await _drain(amqp, queue.dead_letter_key, timeout=2) == [payload]
    finally:
        await _delete_topology(amqp, queue)


async def test_declare_is_idempotent(amqp: aio_pika.abc.AbstractChannel) -> None:
    broker = RabbitBroker(BROKER_URL)
    topology = ConsumerTopology(broker, getLogger("test.consumer-topology"), FAST_RETRIES)
    suffix = uuid4().hex[:8]
    queue = topology.queue(name=f"test.topology.{suffix}", routing_key="x", dead_letter_key=f"test.topology.{suffix}.dlq")
    try:
        await topology.declare()
        await topology.declare()  # a restarted consumer redeclares everything
        for name in (queue.dead_letter_key, *(q.name for q in queue.retry_queues)):
            await amqp.declare_queue(name, passive=True)
    finally:
        await broker.stop()
        for name in (queue.dead_letter_key, *(q.name for q in queue.retry_queues)):
            await amqp.queue_delete(name)
