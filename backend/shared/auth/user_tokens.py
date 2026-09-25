"""Ed25519-signed (EdDSA) user access and refresh tokens."""

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from fastapi import HTTPException, status

from shared.auth.signing_keys import Ed25519KeyLoader
from shared.contracts.auth import TokenClaims
from shared.settings import Settings


ALGORITHM = "EdDSA"


class TokenPurpose(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


# Claims this module sets itself; a caller's extra claims may never replace them,
# or an "extra" {"purpose": "access"} would turn a refresh token into an access one.
_RESERVED_CLAIMS = frozenset({"sub", "id", "role", "purpose", "iss", "aud", "iat", "exp", "jti"})
_REQUIRED_CLAIMS = ["sub", "id", "purpose", "iss", "aud", "iat", "exp", "jti"]

type ClaimValue = str | int | float | bool | None


class UserTokenIssuer:
    """
    Signs user tokens. Holds the private key, so only user-service builds one:
    no other process can mint a session, whatever else it is given.
    """

    def __init__(self, private_key: Ed25519PrivateKey, issuer: str, audience: str) -> None:
        self._private_key = private_key
        self._issuer = issuer
        self._audience = audience

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        return cls(
            private_key=Ed25519KeyLoader.private_key(
                settings.USER_TOKEN_SIGNING_KEY_PEM, "USER_TOKEN_PRIVATE_KEY"
            ),
            issuer=settings.USER_TOKEN_ISSUER,
            audience=settings.USER_TOKEN_AUDIENCE,
        )

    def issue(
        self,
        *,
        email: str,
        user_id: UUID,
        role: str | None,
        purpose: TokenPurpose,
        expires_delta: timedelta,
        extra_claims: Mapping[str, ClaimValue] | None = None,
    ) -> tuple[str, int]:
        """Return ``(token, expiry as a unix timestamp)``."""
        if extra_claims and (clashing := _RESERVED_CLAIMS.intersection(extra_claims)):
            raise ValueError(f"extra_claims may not override {sorted(clashing)}")
        issued_at = datetime.now(timezone.utc)
        expires_at = int((issued_at + expires_delta).timestamp())
        payload: dict[str, ClaimValue] = {
            **(extra_claims or {}),
            "sub": email,
            "id": str(user_id),
            "role": role,
            "purpose": purpose.value,
            "iss": self._issuer,
            "aud": self._audience,
            "iat": int(issued_at.timestamp()),
            "exp": expires_at,
            # Unique per token: two refresh tokens issued for one user within
            # the same second would otherwise be identical, and share a Redis key.
            "jti": uuid4().hex,
        }
        return jwt.encode(payload, self._private_key, algorithm=ALGORITHM), expires_at


class UserTokenVerifier:
    """Checks user tokens with the public key only — what the gateway holds."""

    def __init__(self, public_key: Ed25519PublicKey, issuer: str, audience: str) -> None:
        self._public_key = public_key
        self._issuer = issuer
        self._audience = audience

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        return cls(
            public_key=Ed25519KeyLoader.public_key(
                settings.USER_TOKEN_VERIFYING_KEY_PEM, "USER_TOKEN_PUBLIC_KEY"
            ),
            issuer=settings.USER_TOKEN_ISSUER,
            audience=settings.USER_TOKEN_AUDIENCE,
        )

    def decode(self, token: str, required_purpose: TokenPurpose = TokenPurpose.ACCESS) -> TokenClaims:
        """
        Verify signature, expiry, issuer, audience and purpose.

        Raises:
            HTTPException: 401 for any token that fails a check. The reason is
            deliberately generic: which check failed is useful to an attacker.
        """
        try:
            payload = jwt.decode(
                token,
                self._public_key,
                # Pinned: the algorithm is never taken from the token's own header.
                algorithms=[ALGORITHM],
                issuer=self._issuer,
                audience=self._audience,
                options={"require": _REQUIRED_CLAIMS},
            )
        except jwt.ExpiredSignatureError:
            raise self._unauthorized("Token has expired")
        except jwt.InvalidTokenError:
            raise self._unauthorized("Invalid token")

        if payload.get("purpose") != required_purpose.value:
            raise self._unauthorized("Invalid token purpose")
        try:
            return TokenClaims(
                email=payload["sub"],
                id=payload["id"],
                role=payload.get("role"),
                purpose=payload["purpose"],
                token_version=payload.get("ver"),
            )
        except ValueError:  # pydantic: malformed email or id in a validly signed token
            raise self._unauthorized("Invalid token")

    def is_valid(self, token: str, required_purpose: TokenPurpose = TokenPurpose.ACCESS) -> bool:
        try:
            self.decode(token, required_purpose)
        except HTTPException:
            return False
        return True

    @staticmethod
    def _unauthorized(detail: str) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
