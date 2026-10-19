"""Proof that a sign-up, sign-in or reset request came from a person, not a script.

The storefront's forms carry a Cloudflare Turnstile widget; the token it hands
the browser is checked here, once, with Cloudflare's siteverify API before the
request does anything (creates an account, checks a password, sends an email).
"""

from logging import Logger
from typing import Final, Protocol
from uuid import uuid4

from httpx import AsyncClient, HTTPError

from exceptions.user_exceptions import HumanCheckFailedError, HumanCheckUnavailableError


class HumanCheck(Protocol):
    """Raises unless ``token`` proves a person solved the challenge."""

    async def verify(self, token: str | None) -> None: ...


class TurnstileHumanCheck:
    """Cloudflare Turnstile's server-side validation (siteverify)."""

    VERIFY_URL: Final[str] = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    # Cloudflare's documented maximum; anything longer cannot be a real token.
    MAX_TOKEN_LENGTH: Final[int] = 2048
    # One retry on a network failure. Both attempts send the same idempotency
    # key, so Cloudflare answers the retry from the first attempt instead of
    # reporting the token as already spent.
    ATTEMPTS: Final[int] = 2

    def __init__(self, secret: str, http_client: AsyncClient, logger: Logger,
                 verify_url: str = VERIFY_URL) -> None:
        self._secret = secret
        self._http = http_client
        self._logger = logger
        self._verify_url = verify_url

    async def verify(self, token: str | None) -> None:
        if not token or len(token) > self.MAX_TOKEN_LENGTH:
            raise HumanCheckFailedError()
        payload = {"secret": self._secret, "response": token, "idempotency_key": str(uuid4())}

        answer: dict[str, object] | None = None
        for _ in range(self.ATTEMPTS):
            try:
                response = await self._http.post(self._verify_url, data=payload)
                response.raise_for_status()
                answer = response.json()
                break
            except (HTTPError, ValueError) as exc:
                # Not the visitor's fault: say so, rather than "try again" as if
                # they had failed the challenge.
                self._logger.warning(f"Turnstile siteverify failed: {type(exc).__name__}: {exc}")
        if answer is None:
            raise HumanCheckUnavailableError()

        if answer.get("success") is not True:
            # timeout-or-duplicate (expired or reused token), invalid-input-response, ...
            self._logger.info(f"Turnstile refused a token: {answer.get('error-codes')}")
            raise HumanCheckFailedError()
