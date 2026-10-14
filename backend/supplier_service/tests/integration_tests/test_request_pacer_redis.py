"""
RedisRequestPacer against a real Redis: one budget shared by separate pacers
(as separate processes would hold), customer-facing calls ahead of
background work, and the per-process fallback when Redis is unreachable.
Real time with a short interval; each test uses a key of its own.
"""

import asyncio
from collections.abc import AsyncIterator
from logging import getLogger
from time import monotonic
from uuid import uuid4

import pytest
from redis import asyncio as aioredis

from infrastructure.resilience.request_pacer import LocalRequestPacer, PacingBudget, RedisRequestPacer
from settings import Settings

INTERVAL = 0.1
# asyncio.sleep can wake a little early or late; Redis counts whole milliseconds.
TOLERANCE = 0.015
LOGGER = getLogger("test.request-pacer")


@pytest.fixture
def redis_url() -> str:
    return Settings().SUPPLIER_SERVICE_REDIS_URL


@pytest.fixture
async def key(redis_url: str) -> AsyncIterator[str]:
    key = f"test:cj-pacer:{uuid4().hex}"
    yield key
    redis = aioredis.from_url(redis_url)
    await redis.delete(key)
    await redis.aclose()


def _pacer(redis_url: str, key: str) -> RedisRequestPacer:
    return RedisRequestPacer(
        redis_url=redis_url, key=key, interval=INTERVAL, fallback=LocalRequestPacer(INTERVAL), logger=LOGGER
    )


async def _send(pacer: RedisRequestPacer, budget: PacingBudget, label: str, sent: list[tuple[float, str]]) -> None:
    await pacer.acquire(budget)
    sent.append((monotonic(), label))


async def test_separate_processes_share_one_budget(redis_url: str, key: str) -> None:
    first, second = _pacer(redis_url, key), _pacer(redis_url, key)
    budget = PacingBudget(max_wait=5.0, max_ahead=5.0)
    sent: list[tuple[float, str]] = []
    try:
        await asyncio.gather(*(_send(pacer, budget, "call", sent) for pacer in [first, second] * 3))
    finally:
        await first.close()
        await second.close()

    times = sorted(at for at, _ in sent)
    gaps = [later - earlier for earlier, later in zip(times, times[1:])]
    assert len(times) == 6
    assert min(gaps) >= INTERVAL - TOLERANCE


async def test_a_customer_facing_call_goes_ahead_of_queued_background_work(redis_url: str, key: str) -> None:
    background_pacer, api_pacer = _pacer(redis_url, key), _pacer(redis_url, key)
    background = PacingBudget(max_wait=5.0, max_ahead=INTERVAL)
    interactive = PacingBudget(max_wait=2.0, max_ahead=2.0)
    sent: list[tuple[float, str]] = []

    async def customer_arrives() -> None:
        await asyncio.sleep(INTERVAL / 2)  # background work is already waiting
        await _send(api_pacer, interactive, "customer", sent)

    try:
        await asyncio.gather(
            *(_send(background_pacer, background, "background", sent) for _ in range(4)),
            customer_arrives(),
        )
    finally:
        await background_pacer.close()
        await api_pacer.close()

    order = [label for _, label in sorted(sent)]
    # Two background calls had taken the slots within one interval before the
    # customer arrived; the other two were refused and came back later.
    assert order.index("customer") <= 2, order


async def test_the_slot_key_expires_after_use(redis_url: str, key: str) -> None:
    pacer = _pacer(redis_url, key)
    try:
        await pacer.acquire(PacingBudget(max_wait=1.0, max_ahead=1.0))
    finally:
        await pacer.close()
    redis = aioredis.from_url(redis_url)
    try:
        ttl_ms = await redis.pttl(key)
    finally:
        await redis.aclose()
    assert 0 < ttl_ms <= INTERVAL * 1000 + 60_000


async def test_without_redis_the_process_paces_itself(caplog: pytest.LogCaptureFixture) -> None:
    # Nothing listens on port 1: every Redis call fails at once.
    pacer = RedisRequestPacer(
        redis_url="redis://127.0.0.1:1/0", key="unreachable", interval=INTERVAL,
        fallback=LocalRequestPacer(INTERVAL), logger=LOGGER,
    )
    budget = PacingBudget(max_wait=2.0, max_ahead=2.0)
    sent: list[tuple[float, str]] = []
    with caplog.at_level("WARNING", logger=LOGGER.name):
        try:
            for _ in range(3):
                await _send(pacer, budget, "call", sent)
        finally:
            await pacer.close()

    times = [at for at, _ in sent]
    assert min(later - earlier for earlier, later in zip(times, times[1:])) >= INTERVAL - TOLERANCE
    # One warning for the outage, not one per call.
    assert len([r for r in caplog.records if "falls back" in r.getMessage()]) == 1
