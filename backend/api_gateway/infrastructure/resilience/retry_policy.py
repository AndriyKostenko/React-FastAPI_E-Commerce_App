"""Bounded retries with exponential backoff and full jitter."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from logging import Logger
from random import random


class RetryableError(Exception):
    """
    A failure worth retrying. ``retry_after`` is the server's own hint (a
    ``Retry-After`` header) in seconds, when it gave one.
    """

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """
    ``max_attempts`` counts the first try: 3 means one call and two retries.

    Delays grow exponentially from ``base_delay`` up to ``max_delay``, with
    full jitter (a random delay between zero and that ceiling) so many callers
    that failed together do not retry together. A server's ``Retry-After`` is
    honoured when it is longer, still capped at ``max_delay``.
    """

    max_attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 8.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.base_delay < 0 or self.max_delay < self.base_delay:
            raise ValueError("invalid retry policy")

    def delay_before(self, retry_number: int, retry_after: float | None = None) -> float:
        """Delay before retry ``retry_number`` (1 = the first retry)."""
        ceiling = min(self.max_delay, self.base_delay * (2 ** (retry_number - 1)))
        delay = random() * ceiling
        if retry_after is not None:
            delay = max(delay, min(retry_after, self.max_delay))
        return delay

    async def run[T](
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        name: str,
        logger: Logger,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> T:
        """
        Run ``operation``, retrying only on ``RetryableError``. Any other
        exception, and the last ``RetryableError``, propagate unchanged.

        Only pass operations that are safe to repeat: a retried write that
        had in fact succeeded is applied twice.
        """
        for attempt in range(1, self.max_attempts + 1):
            try:
                return await operation()
            except RetryableError as error:
                if attempt == self.max_attempts:
                    raise
                delay = self.delay_before(attempt, error.retry_after)
                logger.warning(
                    "%s failed (attempt %s/%s), retrying in %.2fs: %s",
                    name, attempt, self.max_attempts, delay, error,
                )
                await sleep(delay)
        raise AssertionError("unreachable")  # the loop always returns or raises
