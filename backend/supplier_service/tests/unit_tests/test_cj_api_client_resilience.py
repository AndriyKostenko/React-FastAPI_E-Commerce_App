"""
CJ client retries and circuit breaker (bug list 16), through a real httpx
client whose transport scripts CJ's answers — the client's own request,
retry and breaker code all run; only the network is replaced.
"""

from collections.abc import Callable
from logging import getLogger

import httpx
import pytest

from service_layer.cj_api_client import (
    CJDropshippingAPIClient,
    CJDropshippingAPIError,
    CJDropshippingNetworkError,
    CJDropshippingUnavailableError,
)
from shared.resilience import CircuitBreaker, CircuitState, RetryPolicy
from shared.settings import Settings


LOGGER = getLogger("test.cj-resilience")
OK = {"code": 200, "result": True, "data": {"ok": True}}


class ScriptedCJ:
    """Answers each request with the next scripted response, and records it."""

    def __init__(self, *answers: httpx.Response | Callable[[httpx.Request], httpx.Response]) -> None:
        self._answers = list(answers)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self._answers.pop(0) if len(self._answers) > 1 else self._answers[0]
        return answer(request) if callable(answer) else answer


def _client(cj: ScriptedCJ, breaker: CircuitBreaker | None = None) -> CJDropshippingAPIClient:
    settings = Settings()
    client = CJDropshippingAPIClient(
        settings,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(cj)),
        breaker=breaker or CircuitBreaker("cj-test", LOGGER, failure_threshold=5, recovery_timeout=60),
        # Real policy, zero delay: the attempts are what is under test.
        retry_policy=RetryPolicy(max_attempts=3, base_delay=0, max_delay=0),
        logger=LOGGER,
    )
    client._access_token = "token"  # skip the token exchange
    return client


def _refused(_: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused")


async def test_a_read_is_retried_through_a_transient_503() -> None:
    cj = ScriptedCJ(httpx.Response(503), httpx.Response(200, json=OK))
    result = await _client(cj).get_order_detail("CJ-1")
    assert result == OK
    assert len(cj.requests) == 2


async def test_a_payment_is_never_retried() -> None:
    # Retrying pay_balance after a lost response could pay CJ twice.
    cj = ScriptedCJ(httpx.Response(503), httpx.Response(200, json=OK))
    with pytest.raises(CJDropshippingUnavailableError):
        await _client(cj).pay_balance("CJ-1")
    assert len(cj.requests) == 1


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
async def test_no_authoritative_answer_is_unavailable_not_a_rejection(status: int) -> None:
    cj = ScriptedCJ(httpx.Response(status))
    with pytest.raises(CJDropshippingUnavailableError) as exc_info:
        await _client(cj).create_order_v2({"orderNumber": "o-1"})
    # Callers read a network error as "outcome unknown, retry" — never as
    # "CJ refused", which fails and refunds the order.
    assert isinstance(exc_info.value, CJDropshippingNetworkError)


async def test_a_real_rejection_stays_a_rejection() -> None:
    cj = ScriptedCJ(httpx.Response(400, text="bad address"))
    with pytest.raises(CJDropshippingAPIError) as exc_info:
        await _client(cj).create_order_v2({"orderNumber": "o-1"})
    assert not isinstance(exc_info.value, CJDropshippingNetworkError)


async def test_retry_after_is_passed_on() -> None:
    cj = ScriptedCJ(httpx.Response(429, headers={"Retry-After": "7"}))
    with pytest.raises(CJDropshippingUnavailableError) as exc_info:
        await _client(cj).pay_balance("CJ-1")
    assert exc_info.value.retry_after == 7


async def test_the_freight_quote_is_retried_although_it_is_a_post() -> None:
    cj = ScriptedCJ(_refused, httpx.Response(200, json=OK))
    assert await _client(cj).calculate_freight({"startCountryCode": "CN"}) == OK
    assert len(cj.requests) == 2


async def test_repeated_failures_open_the_breaker_and_calls_fail_fast() -> None:
    breaker = CircuitBreaker("cj-test", LOGGER, failure_threshold=3, recovery_timeout=60)
    cj = ScriptedCJ(_refused)
    client = _client(cj, breaker)
    with pytest.raises(CJDropshippingNetworkError):
        await client.get_balance()  # three attempts, three failures
    assert breaker.state is CircuitState.OPEN
    calls_so_far = len(cj.requests)

    with pytest.raises(CJDropshippingUnavailableError):
        await client.pay_balance("CJ-1")
    assert len(cj.requests) == calls_so_far  # refused without calling CJ


async def test_business_errors_do_not_trip_the_breaker() -> None:
    breaker = CircuitBreaker("cj-test", LOGGER, failure_threshold=2, recovery_timeout=60)
    cj = ScriptedCJ(httpx.Response(200, json={"code": 1600100, "result": False, "message": "no stock"}))
    client = _client(cj, breaker)
    for _ in range(4):
        with pytest.raises(CJDropshippingAPIError):
            await client.confirm_order("CJ-1")
    assert breaker.state is CircuitState.CLOSED
