"""
Spacing calls to an API that allows one request per interval per account.

Every caller reserves the next free slot (now, or one interval after the last
reserved one) and sleeps until it. ``max_ahead`` is how far ahead a caller may
reserve: a customer-facing call may queue up to its whole wait, while
background work takes a slot only when the queue is about empty, so it never
stands in front of a customer for long. ``max_wait`` bounds the whole wait;
past it the call is refused with ``PacingTimeoutError``.

``RedisRequestPacer`` keeps the slot in Redis, shared by every process using
one key; when Redis cannot be reached it paces through a ``LocalRequestPacer``,
which spaces only the calls of its own process.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from logging import Logger
from random import random
from time import monotonic
from typing import Protocol

from redis import asyncio as aioredis
from redis.exceptions import RedisError


class PacingTimeoutError(Exception):
    """No slot within the caller's wait. ``retry_after``: when one may be free, in seconds."""

    def __init__(self, waited: float, retry_after: float) -> None:
        super().__init__(f"no request slot within {waited:.1f}s; next one in about {retry_after:.1f}s")
        self.waited = waited
        self.retry_after = retry_after


@dataclass(frozen=True, slots=True)
class PacingBudget:
    """How long one call may wait for a slot, and how far ahead it may reserve one."""

    max_wait: float
    max_ahead: float

    def __post_init__(self) -> None:
        if self.max_wait < 0 or self.max_ahead < 0:
            raise ValueError("invalid pacing budget")


class RequestPacer(Protocol):
    async def acquire(self, budget: PacingBudget) -> None:
        """Return when the caller may send; raise ``PacingTimeoutError`` past the budget."""
        ...

    async def close(self) -> None: ...


class UnpacedRequestPacer:
    """Sends at once: pacing switched off (tests, or an account without a limit)."""

    async def acquire(self, budget: PacingBudget) -> None:
        return None

    async def close(self) -> None:
        return None


# A refused caller retries a little after the queue should have shortened, at
# a random point so that refused callers do not all come back together.
_RETRY_JITTER_SECONDS = 0.2


async def _pace(
    budget: PacingBudget,
    reserve: Callable[[float], Awaitable[tuple[bool, float]]],
    clock: Callable[[], float],
    sleep: Callable[[float], Awaitable[None]],
) -> None:
    """
    The waiting loop both pacers share. ``reserve(max_ahead)`` either takes a
    slot and returns ``(True, seconds until it)``, or returns ``(False,
    seconds until a slot would be within max_ahead)`` without taking one.
    """
    started = clock()
    while True:
        remaining = budget.max_wait - (clock() - started)
        # Never reserve a slot the caller would give up before reaching.
        ahead = max(0.0, min(budget.max_ahead, remaining))
        reserved, delay = await reserve(ahead)
        if reserved:
            await sleep(delay)
            return
        # The free slot is ``delay + ahead`` away. Past the remaining wait it
        # cannot be reached even if nobody else takes a slot meanwhile.
        if delay + ahead > remaining:
            raise PacingTimeoutError(clock() - started, delay + ahead)
        await sleep(min(remaining, delay + random() * _RETRY_JITTER_SECONDS))


class LocalRequestPacer:
    """
    Spaces the calls of one process. Holds no asyncio primitive, so one
    instance can serve every event loop of the process: between reading and
    moving the next slot there is no ``await``, so coroutines cannot interleave.
    """

    def __init__(
        self,
        interval: float,
        *,
        clock: Callable[[], float] = monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if interval <= 0:
            raise ValueError("interval must be positive")
        self._interval = interval
        self._clock = clock
        self._sleep = sleep
        self._next_slot = 0.0

    async def acquire(self, budget: PacingBudget) -> None:
        await _pace(budget, self._reserve, self._clock, self._sleep)

    async def _reserve(self, max_ahead: float) -> tuple[bool, float]:
        now = self._clock()
        slot = max(now, self._next_slot)
        if slot - now > max_ahead:
            return False, slot - now - max_ahead
        self._next_slot = slot + self._interval
        return True, slot - now

    async def close(self) -> None:
        return None


# Reserves the next slot atomically, on Redis's clock so that every process
# agrees on "now". Milliseconds: Lua numbers are doubles, and Redis stores a
# number through a 14-significant-digit format, which keeps a millisecond
# epoch (13 digits) exact but would round a microsecond one.
#   KEYS[1] next free slot (epoch ms)
#   ARGV[1] interval ms, ARGV[2] max_ahead ms
# Returns {1, ms until the reserved slot} or {0, ms until one is within max_ahead}.
_RESERVE_SCRIPT = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
local slot = tonumber(redis.call('GET', KEYS[1]) or '0')
if slot < now then slot = now end
local wait = slot - now
local max_ahead = tonumber(ARGV[2])
if wait > max_ahead then
  return {0, wait - max_ahead}
end
local interval = tonumber(ARGV[1])
-- The key outlives the last reservation by a minute, then disappears.
redis.call('SET', KEYS[1], slot + interval, 'PX', wait + interval + 60000)
return {1, wait}
"""


class RedisRequestPacer:
    """
    Spaces the calls of every process that shares ``key``. Falls back to the
    process's ``LocalRequestPacer`` while Redis cannot be reached: calls go on,
    only collisions with other processes come back.
    """

    def __init__(
        self,
        *,
        redis_url: str,
        key: str,
        interval: float,
        fallback: LocalRequestPacer,
        logger: Logger,
        clock: Callable[[], float] = monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        redis_timeout_seconds: float = 1.0,
    ) -> None:
        if interval <= 0:
            raise ValueError("interval must be positive")
        self._redis_url = redis_url
        self._key = key
        self._interval_ms = max(1, round(interval * 1000))
        self._fallback = fallback
        self._logger = logger
        self._clock = clock
        self._sleep = sleep
        self._redis_timeout = redis_timeout_seconds
        self._redis: aioredis.Redis | None = None
        self._degraded = False

    async def acquire(self, budget: PacingBudget) -> None:
        started = self._clock()
        try:
            await _pace(budget, self._reserve, self._clock, self._sleep)
        except (RedisError, OSError, TimeoutError) as error:
            if not self._degraded:
                self._degraded = True
                self._logger.warning(
                    "Request pacing for %s falls back to this process only: Redis unavailable (%s)",
                    self._key, error,
                )
            # Whatever was already spent waiting on Redis counts against the budget.
            spent = self._clock() - started
            await self._fallback.acquire(
                PacingBudget(max_wait=max(0.0, budget.max_wait - spent), max_ahead=budget.max_ahead)
            )
            return
        if self._degraded:
            self._degraded = False
            self._logger.info("Request pacing for %s shared through Redis again", self._key)

    async def _reserve(self, max_ahead: float) -> tuple[bool, float]:
        reserved, milliseconds = await self._client().eval(
            _RESERVE_SCRIPT, 1, self._key, self._interval_ms, int(max_ahead * 1000)
        )
        return bool(reserved), int(milliseconds) / 1000

    def _client(self) -> aioredis.Redis:
        # Connects on first use: building a pacer does no I/O.
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._redis_url,
                socket_timeout=self._redis_timeout,
                socket_connect_timeout=self._redis_timeout,
            )
        return self._redis

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
