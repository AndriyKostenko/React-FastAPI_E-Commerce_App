"""
The gateway's signed statement of who a proxied request is acting for.

The gateway checks the user's token, then signs a short-lived assertion with
its own Ed25519 key; each service verifies it with the gateway's public key.
Services therefore never see or re-check the user's token (they could not:
they do not hold its key), and a request that did not pass through the gateway
cannot claim an identity — without a valid assertion it is simply anonymous.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Self
from uuid import UUID, uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from shared.auth.signing_keys import Ed25519KeyLoader
from shared.contracts.auth import TokenClaims
from shared.settings import Settings
from shared.utils.authenticated_caller import AuthenticatedCaller


CALLER_ASSERTION_HEADER = "X-Caller-Assertion"
ALGORITHM = "EdDSA"
_REQUIRED_CLAIMS = ["iss", "aud", "iat", "exp", "jti", "htm", "htu"]
# Tolerates clock drift between the gateway's host and a service's.
_CLOCK_SKEW = timedelta(seconds=5)


class InvalidCallerAssertion(Exception):
    """The assertion is forged, expired, or was issued for a different request."""


@dataclass(frozen=True, slots=True)
class RequestTarget:
    """
    The downstream request an assertion is valid for.

    Binding the assertion to method and path means one captured on the
    internal network cannot be replayed against another route while it lives.
    """

    method: str
    path: str

    def normalised(self) -> tuple[str, str]:
        return self.method.upper(), self.path.rstrip("/") or "/"


class CallerAssertionSigner:
    """Held by the gateway alone: the only process that can speak for a user."""

    def __init__(
        self, private_key: Ed25519PrivateKey, issuer: str, audience: str, ttl: timedelta
    ) -> None:
        self._private_key = private_key
        self._issuer = issuer
        self._audience = audience
        self._ttl = ttl

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        return cls(
            private_key=Ed25519KeyLoader.private_key(
                settings.GATEWAY_ASSERTION_SIGNING_KEY_PEM, "GATEWAY_ASSERTION_PRIVATE_KEY"
            ),
            issuer=settings.GATEWAY_ASSERTION_ISSUER,
            audience=settings.GATEWAY_ASSERTION_AUDIENCE,
            ttl=timedelta(seconds=settings.GATEWAY_ASSERTION_TTL_SECONDS),
        )

    def sign(self, caller: TokenClaims | None, target: RequestTarget) -> str:
        """Sign for ``caller`` (None for an anonymous request) and this one target."""
        method, path = target.normalised()
        issued_at = datetime.now(timezone.utc)
        payload: dict[str, str | int | None] = {
            "iss": self._issuer,
            "aud": self._audience,
            "iat": int(issued_at.timestamp()),
            "exp": int((issued_at + self._ttl).timestamp()),
            "jti": uuid4().hex,
            "htm": method,
            "htu": path,
        }
        if caller is not None:
            payload |= {"sub": str(caller.id), "email": str(caller.email), "role": caller.role}
        return jwt.encode(payload, self._private_key, algorithm=ALGORITHM)


class CallerAssertionVerifier:
    """Held by every service: the gateway's public key, never its private one."""

    def __init__(self, public_key: Ed25519PublicKey, issuer: str, audience: str) -> None:
        self._public_key = public_key
        self._issuer = issuer
        self._audience = audience

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        return cls(
            public_key=Ed25519KeyLoader.public_key(
                settings.GATEWAY_ASSERTION_VERIFYING_KEY_PEM, "GATEWAY_ASSERTION_PUBLIC_KEY"
            ),
            issuer=settings.GATEWAY_ASSERTION_ISSUER,
            audience=settings.GATEWAY_ASSERTION_AUDIENCE,
        )

    def verify(self, assertion: str, target: RequestTarget) -> AuthenticatedCaller:
        try:
            claims = jwt.decode(
                assertion,
                self._public_key,
                algorithms=[ALGORITHM],
                issuer=self._issuer,
                audience=self._audience,
                leeway=_CLOCK_SKEW,
                options={"require": _REQUIRED_CLAIMS},
            )
        except jwt.InvalidTokenError as error:
            raise InvalidCallerAssertion(str(error)) from error

        if (claims["htm"], claims["htu"]) != target.normalised():
            raise InvalidCallerAssertion("assertion was issued for a different request")

        subject = claims.get("sub")
        if subject is None:
            return AuthenticatedCaller()  # a request the gateway passed through anonymously
        try:
            user_id = UUID(subject)
        except ValueError as error:
            raise InvalidCallerAssertion("assertion subject is not a user id") from error
        return AuthenticatedCaller(user_id=user_id, email=claims.get("email"), role=claims.get("role"))
