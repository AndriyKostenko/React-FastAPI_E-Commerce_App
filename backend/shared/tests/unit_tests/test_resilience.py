"""CircuitBreaker and RetryPolicy, driven by a controllable clock and sleep."""

from logging import getLogger

import pytest

from shared.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    RetryableError,
    RetryPolicy,
)


LOGGER = getLogger("test.resilience")


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _breaker(clock: FakeClock, threshold: int = 3) -> CircuitBreaker:
    return CircuitBreaker("svc", LOGGER, failure_threshold=threshold, recovery_timeout=30, clock=clock)


class TestCircuitBreaker:
    def test_opens_after_consecutive_failures_and_fails_fast(self) -> None:
        clock = FakeClock()
        breaker = _breaker(clock)
        for _ in range(3):
            breaker.before_call()
            breaker.record_failure()
        assert breaker.state is CircuitState.OPEN
        with pytest.raises(CircuitOpenError) as exc_info:
            breaker.before_call()
        assert 0 < exc_info.value.retry_after <= 30

    def test_a_success_resets_the_failure_count(self) -> None:
        breaker = _breaker(FakeClock())
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state is CircuitState.CLOSED

    def test_after_cooldown_one_trial_call_decides(self) -> None:
        clock = FakeClock()
        breaker = _breaker(clock, threshold=1)
        breaker.record_failure()
        clock.now += 31

        breaker.before_call()  # the trial
        assert breaker.state is CircuitState.HALF_OPEN
        with pytest.raises(CircuitOpenError):
            breaker.before_call()  # a second concurrent caller is still refused

        breaker.record_success()
        assert breaker.state is CircuitState.CLOSED
        breaker.before_call()

    def test_a_failed_trial_reopens_for_a_full_cooldown(self) -> None:
        clock = FakeClock()
        breaker = _breaker(clock, threshold=1)
        breaker.record_failure()
        clock.now += 31
        breaker.before_call()
        breaker.record_failure()
        assert breaker.state is CircuitState.OPEN
        clock.now += 29
        with pytest.raises(CircuitOpenError):
            breaker.before_call()

    def test_separate_breakers_do_not_share_state(self) -> None:
        clock = FakeClock()
        failing, healthy = _breaker(clock, threshold=1), _breaker(clock, threshold=1)
        failing.record_failure()
        healthy.before_call()  # one dependency down must not trip another


class TestRetryPolicy:
    async def test_retries_retryable_errors_then_succeeds(self) -> None:
        calls, sleeps = [], []

        async def flaky() -> str:
            calls.append(1)
            if len(calls) < 3:
                raise RetryableError("503")
            return "ok"

        async def record(delay: float) -> None:
            sleeps.append(delay)

        result = await RetryPolicy(max_attempts=3).run(flaky, name="op", logger=LOGGER, sleep=record)
        assert result == "ok"
        assert len(calls) == 3 and len(sleeps) == 2

    async def test_gives_up_after_max_attempts(self) -> None:
        calls = []

        async def always_down() -> None:
            calls.append(1)
            raise RetryableError("503")

        async def no_wait(_: float) -> None:
            return None

        with pytest.raises(RetryableError):
            await RetryPolicy(max_attempts=3).run(always_down, name="op", logger=LOGGER, sleep=no_wait)
        assert len(calls) == 3

    async def test_other_errors_are_not_retried(self) -> None:
        calls = []

        async def rejected() -> None:
            calls.append(1)
            raise ValueError("400 bad request")

        with pytest.raises(ValueError):
            await RetryPolicy(max_attempts=3).run(rejected, name="op", logger=LOGGER)
        assert len(calls) == 1

    def test_backoff_is_capped_and_honours_retry_after(self) -> None:
        policy = RetryPolicy(max_attempts=10, base_delay=0.5, max_delay=8.0)
        assert all(0 <= policy.delay_before(n) <= 8.0 for n in range(1, 10))
        assert policy.delay_before(1, retry_after=5) >= 5
        assert policy.delay_before(1, retry_after=60) == 8.0  # never beyond the cap
