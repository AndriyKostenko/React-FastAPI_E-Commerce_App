"""UsdCadRate: Bank of Canada parsing, caching, and staying safe when the feed misbehaves."""

from decimal import Decimal
from logging import getLogger

import httpx

from shared.utils.exchange_rates import UsdCadRate


FALLBACK = Decimal("1.38")


def _feed(*answers: httpx.Response | Exception) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    seen: list[httpx.Request] = []
    queue = list(answers)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        answer = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(answer, Exception):
            raise answer
        return answer

    return httpx.MockTransport(handler), seen


def _observation(value: str) -> httpx.Response:
    return httpx.Response(200, json={"observations": [{"d": "2026-09-25", "FXUSDCAD": {"v": value}}]})


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _rate(transport: httpx.MockTransport, clock: Clock | None = None) -> UsdCadRate:
    return UsdCadRate(getLogger("test.fx"), transport=transport, clock=clock or Clock(), ttl_seconds=3600)


async def test_reads_the_bank_of_canada_rate() -> None:
    transport, _ = _feed(_observation("1.4145"))
    assert await _rate(transport).current(fallback=FALLBACK) == Decimal("1.4145")


async def test_the_rate_is_cached_until_the_ttl_passes() -> None:
    clock = Clock()
    transport, seen = _feed(_observation("1.4145"), _observation("1.4200"))
    rate = _rate(transport, clock)

    assert await rate.current(fallback=FALLBACK) == Decimal("1.4145")
    clock.now = 3599
    assert await rate.current(fallback=FALLBACK) == Decimal("1.4145")
    assert len(seen) == 1
    clock.now = 3601
    assert await rate.current(fallback=FALLBACK) == Decimal("1.4200")


async def test_an_implausible_rate_is_not_used() -> None:
    # A decimal slip in the feed must never reprice the catalogue tenfold.
    transport, _ = _feed(_observation("14.145"))
    assert await _rate(transport).current(fallback=FALLBACK) == FALLBACK


async def test_the_feed_being_down_falls_back_to_the_configured_rate() -> None:
    transport, _ = _feed(httpx.ConnectError("unreachable"))
    assert await _rate(transport).current(fallback=FALLBACK) == FALLBACK


async def test_after_one_good_answer_an_outage_keeps_the_last_good_rate() -> None:
    clock = Clock()
    transport, _ = _feed(_observation("1.4145"), httpx.Response(503))
    rate = _rate(transport, clock)
    await rate.current(fallback=FALLBACK)
    clock.now = 7200  # cache expired, feed now failing
    assert await rate.current(fallback=FALLBACK) == Decimal("1.4145")


async def test_fixed_source_never_calls_the_feed() -> None:
    transport, seen = _feed(_observation("1.4145"))
    assert await _rate(transport).current(fallback=Decimal("1.40"), source="fixed") == Decimal("1.40")
    assert seen == []
