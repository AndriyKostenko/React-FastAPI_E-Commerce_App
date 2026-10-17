"""
TurnstileHumanCheck against Cloudflare's real siteverify API.

Cloudflare publishes test secret keys with fixed answers, so the real round
trip is exercised here with no stand-in: always-pass, always-fail and "token
already spent". Needs network access to challenges.cloudflare.com.

Only an outage cannot be produced on demand; that case uses a transport that
fails, at the bottom.
"""
from logging import getLogger

import pytest
from httpx import AsyncClient, ConnectError, MockTransport, Request, Response

from exceptions.user_exceptions import HumanCheckFailedError, HumanCheckUnavailableError
from service_layer.human_check import TurnstileHumanCheck
from settings import get_test_settings

test_settings = get_test_settings()
logger = getLogger("test-human-check")

ALWAYS_PASSES = "1x0000000000000000000000000000000AA"
ALWAYS_FAILS = "2x0000000000000000000000000000000AA"
ALREADY_SPENT = "3x0000000000000000000000000000000AA"


async def _verify_with_cloudflare(secret: str, token: str) -> None:
    # Opened per test: the client must close on the loop that opened it.
    async with AsyncClient(timeout=10) as client:
        await TurnstileHumanCheck(secret, client, logger).verify(token)


async def test_a_solved_challenge_passes() -> None:
    await _verify_with_cloudflare(ALWAYS_PASSES, test_settings.CAPTCHA_TOKEN)


async def test_a_failed_challenge_is_refused() -> None:
    with pytest.raises(HumanCheckFailedError):
        await _verify_with_cloudflare(ALWAYS_FAILS, test_settings.CAPTCHA_TOKEN)


async def test_a_reused_token_is_refused() -> None:
    with pytest.raises(HumanCheckFailedError):
        await _verify_with_cloudflare(ALREADY_SPENT, test_settings.CAPTCHA_TOKEN)


@pytest.mark.parametrize("token", [None, "", "x" * (TurnstileHumanCheck.MAX_TOKEN_LENGTH + 1)])
async def test_a_missing_or_oversized_token_is_refused_without_asking_cloudflare(token: str | None) -> None:
    asked: list[Request] = []
    async with AsyncClient(transport=MockTransport(lambda request: asked.append(request) or Response(200))) as client:
        with pytest.raises(HumanCheckFailedError):
            await TurnstileHumanCheck(ALWAYS_PASSES, client, logger).verify(token)
    assert asked == []


async def test_an_outage_is_reported_as_unavailable_after_one_retry_with_the_same_key() -> None:
    attempts: list[Request] = []

    def unreachable(request: Request) -> Response:
        attempts.append(request)
        raise ConnectError("network down", request=request)

    async with AsyncClient(transport=MockTransport(unreachable)) as client:
        with pytest.raises(HumanCheckUnavailableError):
            await TurnstileHumanCheck(ALWAYS_PASSES, client, logger).verify(test_settings.CAPTCHA_TOKEN)

    assert len(attempts) == TurnstileHumanCheck.ATTEMPTS
    # The retry carries the same idempotency key, so Cloudflare cannot count
    # the token as spent by the first attempt.
    assert len({request.content for request in attempts}) == 1
