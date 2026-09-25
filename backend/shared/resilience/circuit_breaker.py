"""A circuit breaker for calls to one dependency (a service, or CJ's API)."""

from collections.abc import Callable
from enum import StrEnum
from logging import Logger
from time import monotonic


class CircuitState(StrEnum):
    CLOSED = "closed"        # calls flow; failures are counted
    OPEN = "open"            # calls fail fast until the cooldown ends
    HALF_OPEN = "half_open"  # one trial call decides whether to close again


class CircuitOpenError(Exception):
    """Refused without calling: the dependency failed repeatedly and is cooling down."""

    def __init__(self, name: str, retry_after: float) -> None:
        super().__init__(f"{name} is unavailable; retry in {retry_after:.0f}s")
        self.name = name
        self.retry_after = retry_after


class CircuitBreaker:
    """
    Stops hammering a dependency that is down, and stops callers waiting on it.

    ``failure_threshold`` consecutive failures open the circuit; while open,
    ``before_call()`` raises ``CircuitOpenError`` at once instead of letting the
    caller wait out a timeout. After ``recovery_timeout`` seconds one trial call
    is let through: success closes the circuit, failure reopens it.

    One breaker per dependency. The previous gateway breaker was a single
    decorator shared by every service, so one service failing tripped them all.

    State is per process and deliberately so: each gateway worker learns a
    dependency is down from its own calls within a few requests.

    Usage::

        breaker.before_call()          # raises CircuitOpenError when open
        try:
            result = await call()
        except TransientError:
            breaker.record_failure()
            raise
        breaker.record_success()
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if failure_threshold < 1 or recovery_timeout <= 0:
            raise ValueError("failure_threshold must be >= 1 and recovery_timeout > 0")
        self.name = name
        self._logger = logger
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._clock = clock
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = 0.0
        self._trial_in_flight = False

    @property
    def state(self) -> CircuitState:
        return self._state

    def before_call(self) -> None:
        """Admit the call, or raise ``CircuitOpenError`` without making it."""
        if self._state is CircuitState.CLOSED:
            return
        remaining = self._opened_at + self._recovery_timeout - self._clock()
        if self._state is CircuitState.OPEN and remaining > 0:
            raise CircuitOpenError(self.name, remaining)
        # Cooldown over: admit exactly one trial call. The event loop is single
        # threaded, so this check-and-set cannot race between coroutines.
        if self._trial_in_flight:
            raise CircuitOpenError(self.name, self._recovery_timeout)
        self._state = CircuitState.HALF_OPEN
        self._trial_in_flight = True

    def record_success(self) -> None:
        if self._state is not CircuitState.CLOSED:
            self._logger.info("Circuit %s closed: dependency recovered", self.name)
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._trial_in_flight = False

    def record_failure(self) -> None:
        self._trial_in_flight = False
        if self._state is CircuitState.HALF_OPEN:
            self._open("trial call failed")
            return
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_threshold:
            self._open(f"{self._consecutive_failures} consecutive failures")

    def _open(self, reason: str) -> None:
        if self._state is not CircuitState.OPEN:
            self._logger.error(
                "Circuit %s opened (%s); failing fast for %.0fs", self.name, reason, self._recovery_timeout
            )
        self._state = CircuitState.OPEN
        self._opened_at = self._clock()
