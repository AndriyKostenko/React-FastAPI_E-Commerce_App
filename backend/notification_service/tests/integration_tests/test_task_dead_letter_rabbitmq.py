"""
DeadLetteringRetryMiddleware against a real RabbitMQ and a real taskiq
receiver — no mocks: retries travel through the broker's TTL delay queue and
the parked task through a real queue, which is exactly what could go wrong.

Needs the local broker (./local/dev.sh infra up). Every queue and exchange is
uniquely named and deleted afterwards.
"""

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from logging import getLogger
from uuid import uuid4

import aio_pika
import pytest
from aio_pika.abc import ExchangeType
from taskiq.receiver import Receiver
from taskiq_aio_pika import AioPikaBroker, Exchange, Queue

from shared.messaging.task_dead_letter import (
    TASK_ERROR_HEADER,
    TASK_NAME_HEADER,
    DeadLetteringRetryMiddleware,
)
from shared.settings import get_settings


BROKER_URL = get_settings().RABBITMQ_BROKER_URL
MAX_ATTEMPTS = 3


@dataclass
class TaskHarness:
    broker: AioPikaBroker
    dead_letter_queue: str
    attempts: list[int] = field(default_factory=list)


@pytest.fixture
async def harness() -> AsyncGenerator[TaskHarness, None]:
    suffix = uuid4().hex[:8]
    prefix = f"test.taskiq.{suffix}"
    broker = AioPikaBroker(
        url=BROKER_URL,
        exchange=Exchange(name=f"{prefix}.exchange", durable=True, declare=True, type=ExchangeType.TOPIC),
        task_queues=[Queue(name=f"{prefix}.queue", durable=True, declare=True)],
        delay_queue=Queue(name=f"{prefix}.delay", durable=True, declare=True),
        dead_letter_queue=Queue(name=f"{prefix}.rmq_dead_letter", durable=True, declare=True),
    ).with_middlewares(
        DeadLetteringRetryMiddleware(
            dead_letter_queue_name=f"{prefix}.dead_letter",
            logger=getLogger("test.task-dead-letter"),
            default_retry_label=True,
            default_retry_count=MAX_ATTEMPTS,
            default_delay=0.2,
            max_delay_exponent=0.5,
        )
    )
    broker.is_worker_process = True
    harness = TaskHarness(broker=broker, dead_letter_queue=f"{prefix}.dead_letter")
    await broker.startup()
    finish = asyncio.Event()
    receiver_task = asyncio.create_task(Receiver(broker, run_startup=False).listen(finish))
    try:
        yield harness
    finally:
        finish.set()
        receiver_task.cancel()
        await asyncio.gather(receiver_task, return_exceptions=True)
        await broker.shutdown()
        connection = await aio_pika.connect_robust(BROKER_URL)
        async with connection:
            channel = await connection.channel()
            for name in ("queue", "delay", "rmq_dead_letter", "dead_letter"):
                await channel.queue_delete(f"{prefix}.{name}")
            await channel.exchange_delete(f"{prefix}.exchange")


async def _wait_for_attempts(harness: TaskHarness, count: int, timeout: float = 8) -> None:
    async def reached() -> None:
        while len(harness.attempts) < count:
            await asyncio.sleep(0.05)

    await asyncio.wait_for(reached(), timeout=timeout)
    await asyncio.sleep(0.5)  # give the middleware time to publish the parked copy


async def _parked(queue_name: str) -> list[aio_pika.abc.AbstractIncomingMessage]:
    connection = await aio_pika.connect_robust(BROKER_URL)
    async with connection:
        channel = await connection.channel()
        try:
            queue = await channel.declare_queue(queue_name, passive=True)
        except aio_pika.exceptions.ChannelClosed:
            return []  # never declared: nothing was ever parked
        parked: list[aio_pika.abc.AbstractIncomingMessage] = []
        while (incoming := await queue.get(fail=False)) is not None:
            await incoming.ack()
            parked.append(incoming)
        return parked


async def test_exhausted_task_is_retried_then_parked(harness: TaskHarness) -> None:
    @harness.broker.task(task_name=f"always_fails_{uuid4().hex[:6]}")
    async def always_fails(order_id: str) -> None:
        harness.attempts.append(len(harness.attempts))
        raise RuntimeError(f"smtp down for {order_id}")

    await always_fails.kiq("o-42")
    await _wait_for_attempts(harness, MAX_ATTEMPTS)

    assert len(harness.attempts) == MAX_ATTEMPTS  # and no further attempts after giving up
    parked = await _parked(harness.dead_letter_queue)
    assert len(parked) == 1
    assert parked[0].headers[TASK_NAME_HEADER] == always_fails.task_name
    assert "smtp down for o-42" in str(parked[0].headers[TASK_ERROR_HEADER])
    assert b"o-42" in parked[0].body  # the original arguments survive for replay


async def test_task_that_recovers_is_not_parked(harness: TaskHarness) -> None:
    @harness.broker.task(task_name=f"flaky_{uuid4().hex[:6]}")
    async def flaky() -> None:
        harness.attempts.append(len(harness.attempts))
        if len(harness.attempts) < 2:
            raise RuntimeError("transient")

    await flaky.kiq()
    await _wait_for_attempts(harness, 2)

    assert len(harness.attempts) == 2
    assert await _parked(harness.dead_letter_queue) == []


async def test_task_without_retries_is_neither_retried_nor_parked(harness: TaskHarness) -> None:
    # e.g. image generation: its failure refunds quota, it must never re-run.
    @harness.broker.task(task_name=f"no_retry_{uuid4().hex[:6]}", retry_on_error=False)
    async def no_retry() -> None:
        harness.attempts.append(len(harness.attempts))
        raise RuntimeError("provider error")

    await no_retry.kiq()
    await _wait_for_attempts(harness, 1)
    await asyncio.sleep(1)  # a retry, had one been scheduled, would have arrived by now

    assert len(harness.attempts) == 1
    assert await _parked(harness.dead_letter_queue) == []
