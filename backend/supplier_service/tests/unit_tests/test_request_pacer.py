"""
The pacing rules, through LocalRequestPacer on a controllable clock: slots
one interval apart, how far ahead a caller may queue, and when it gives up.
The Redis pacer runs the same loop; it is tested against a real Redis in
integration_tests/test_request_pacer_redis.py.
"""

import pytest

from infrastructure.resilience.request_pacer import LocalRequestPacer, PacingBudget, PacingTimeoutError

INTERVAL = 1.1
INTERACTIVE = PacingBudget(max_wait=3.0, max_ahead=3.0)
BACKGROUND = PacingBudget(max_wait=30.0, max_ahead=INTERVAL)


class FakeTime:
    """A clock that moves only when someone sleeps."""

    def __init__(self) -> None:
        self.now = 0.0

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def time() -> FakeTime:
    return FakeTime()


@pytest.fixture
def pacer(time: FakeTime) -> LocalRequestPacer:
    return LocalRequestPacer(INTERVAL, clock=time.clock, sleep=time.sleep)


async def _queue(pacer: LocalRequestPacer, slots: int) -> None:
    """Other callers reserve ``slots`` slots, as if each were already waiting for its own."""
    for _ in range(slots):
        reserved, _ = await pacer._reserve(max_ahead=1000.0)
        assert reserved


async def test_calls_are_sent_one_interval_apart(pacer: LocalRequestPacer, time: FakeTime) -> None:
    sent = []
    for _ in range(3):
        await pacer.acquire(BACKGROUND)
        sent.append(time.now)
    assert sent == pytest.approx([0.0, 1.1, 2.2])


async def test_a_quiet_moment_is_used_at_once(pacer: LocalRequestPacer, time: FakeTime) -> None:
    await pacer.acquire(BACKGROUND)
    time.now = 10.0  # nothing sent for a while: no slot is owed
    await pacer.acquire(BACKGROUND)
    assert time.now == 10.0


async def test_a_customer_facing_call_queues_behind_reserved_slots(pacer: LocalRequestPacer, time: FakeTime) -> None:
    await _queue(pacer, 2)  # slots at 0.0 and 1.1 are taken
    await pacer.acquire(INTERACTIVE)
    assert time.now == pytest.approx(2.2)


async def test_background_work_waits_until_about_one_slot_is_ahead(pacer: LocalRequestPacer, time: FakeTime) -> None:
    await _queue(pacer, 3)  # the next free slot is at 3.3
    await pacer.acquire(BACKGROUND)
    # It did not reserve 3.3 at once (that is 3.3 ahead): it came back once the
    # queue was down to one interval, and only then took the slot.
    assert time.now == pytest.approx(3.3)


async def test_a_call_that_cannot_reach_a_slot_in_its_wait_is_refused_at_once(
    pacer: LocalRequestPacer, time: FakeTime
) -> None:
    await _queue(pacer, 5)  # the next free slot is at 5.5
    with pytest.raises(PacingTimeoutError) as exc_info:
        await pacer.acquire(INTERACTIVE)
    assert time.now == 0.0  # it did not wait for a slot it would never reach
    assert exc_info.value.retry_after == pytest.approx(5.5)
    # and took none: the next caller is not pushed further back
    reserved, delay = await pacer._reserve(max_ahead=1000.0)
    assert reserved and delay == pytest.approx(5.5)


async def test_background_work_gives_up_at_its_wait(time: FakeTime) -> None:
    pacer = LocalRequestPacer(INTERVAL, clock=time.clock, sleep=time.sleep)
    await _queue(pacer, 10)  # the next free slot is at 11.0
    with pytest.raises(PacingTimeoutError):
        await pacer.acquire(PacingBudget(max_wait=5.0, max_ahead=INTERVAL))
    assert time.now <= 5.0


async def test_no_wait_at_all_still_gets_a_free_slot(pacer: LocalRequestPacer, time: FakeTime) -> None:
    await pacer.acquire(PacingBudget(max_wait=0.0, max_ahead=0.0))
    assert time.now == 0.0
    with pytest.raises(PacingTimeoutError):
        await pacer.acquire(PacingBudget(max_wait=0.0, max_ahead=0.0))


def test_invalid_settings_are_refused() -> None:
    with pytest.raises(ValueError):
        LocalRequestPacer(0)
    with pytest.raises(ValueError):
        PacingBudget(max_wait=-1.0, max_ahead=0.0)
