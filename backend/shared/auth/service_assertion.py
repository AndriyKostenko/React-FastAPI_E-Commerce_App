"""
Service-to-service identity (bug list 5).

Some internal routes are called by another service directly, with no user
behind the request (order-service asking product-service for a quote). Only
the gateway can assert a *user*, so these calls used to arrive anonymous and
were protected by nothing but the private network.

Now the calling service signs a short-lived assertion with its own Ed25519
key — the same format as the gateway's caller assertion, issued by the service
itself and bound to the exact method and path — and the called service
accepts it only from the services a route allows.
"""

from collections.abc import Callable, Generator
from datetime import timedelta
from logging import getLogger
from typing import Self

import httpx
from fastapi import HTTPException, Request, status

from shared.auth.caller_assertion import (
    CallerAssertionSigner,
    CallerAssertionVerifier,
    InvalidCallerAssertion,
    RequestTarget,
)
from shared.auth.signing_keys import Ed25519KeyLoader, SigningKeyError
from shared.settings import Settings, get_settings


SERVICE_ASSERTION_HEADER = "X-Service-Assertion"
SERVICE_ASSERTION_AUDIENCE = "internal-services"
_TTL = timedelta(seconds=60)
_logger = getLogger("shared.service-assertion")


class _ServiceKeys:
    """Which settings hold each calling service's keypair. One caller today."""

    PRIVATE = {"order-service": "ORDER_SERVICE_ASSERTION_PRIVATE_KEY"}
    PUBLIC = {"order-service": "ORDER_SERVICE_ASSERTION_PUBLIC_KEY"}

    @classmethod
    def private_pem(cls, settings: Settings, service: str) -> str:
        return cls._reveal(settings, cls.PRIVATE[service])

    @classmethod
    def public_pem(cls, settings: Settings, service: str) -> str:
        return cls._reveal(settings, cls.PUBLIC[service])

    @staticmethod
    def _reveal(settings: Settings, name: str) -> str:
        value = getattr(settings, name, None)
        if value is None:
            raise SigningKeyError(f"{name} is not configured")
        return value.get_secret_value() if hasattr(value, "get_secret_value") else str(value)


class ServiceAssertionAuth(httpx.Auth):
    """
    ``auth=`` for an internal httpx client: each request carries an assertion
    that this service made it, bound to that request's method and path.
    """

    def __init__(self, signer_factory: Callable[[], CallerAssertionSigner]) -> None:
        self._signer_factory = signer_factory
        self._signer: CallerAssertionSigner | None = None

    @classmethod
    def for_service(cls, settings: Settings, service: str) -> Self:
        # Built on first use, so a process can start before its key is added;
        # a call made without one fails loudly instead of going out unsigned.
        return cls(
            lambda: CallerAssertionSigner(
                private_key=Ed25519KeyLoader.private_key(
                    _ServiceKeys.private_pem(settings, service), _ServiceKeys.PRIVATE[service]
                ),
                issuer=service,
                audience=SERVICE_ASSERTION_AUDIENCE,
                ttl=_TTL,
            )
        )

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        signer = self._signer
        if signer is None:
            signer = self._signer = self._signer_factory()
        target = RequestTarget(method=request.method, path=request.url.path)
        request.headers[SERVICE_ASSERTION_HEADER] = signer.sign(None, target)
        yield request


class ServiceCallerGuard:
    """
    FastAPI dependency admitting only requests signed by one of ``allowed``.

    Verifiers are built from each caller's public key on first use and cached.
    A missing key, a missing header, or an assertion that does not verify is a
    401 — the route fails closed.
    """

    def __init__(self, *allowed: str, settings_provider: Callable[[], Settings] = get_settings) -> None:
        self._allowed = allowed
        self._settings_provider = settings_provider
        self._verifiers: dict[str, CallerAssertionVerifier] = {}

    def _verifier(self, service: str) -> CallerAssertionVerifier:
        if service not in self._verifiers:
            settings = self._settings_provider()
            self._verifiers[service] = CallerAssertionVerifier(
                public_key=Ed25519KeyLoader.public_key(
                    _ServiceKeys.public_pem(settings, service), _ServiceKeys.PUBLIC[service]
                ),
                issuer=service,
                audience=SERVICE_ASSERTION_AUDIENCE,
            )
        return self._verifiers[service]

    def __call__(self, request: Request) -> str:
        assertion = request.headers.get(SERVICE_ASSERTION_HEADER)
        if assertion is None:
            raise self._refused("Service authentication required")
        target = RequestTarget(method=request.method, path=request.url.path)
        for service in self._allowed:
            try:
                self._verifier(service).verify(assertion, target)
            except SigningKeyError as error:
                _logger.error("Cannot verify calls from %s: %s", service, error)
                continue
            except InvalidCallerAssertion:
                continue
            return service
        raise self._refused("Invalid service assertion")

    @staticmethod
    def _refused(detail: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def require_service(*allowed: str) -> ServiceCallerGuard:
    """``Depends(require_service("order-service"))`` on a service-to-service route."""
    return ServiceCallerGuard(*allowed)
