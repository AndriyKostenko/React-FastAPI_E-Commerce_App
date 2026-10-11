"""Ed25519-signed (EdDSA) user tokens: the verifier only.

The gateway checks tokens with user-service's public key; only user-service
holds the issuer (and the private key).
"""

from enum import StrEnum
from typing import Self

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PublicKey,
)
from fastapi import HTTPException, status

from infrastructure.auth.signing_keys import Ed25519KeyLoader
from contracts.auth import TokenClaims
from settings import Settings


ALGORITHM = "EdDSA"


class TokenPurpose(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


_REQUIRED_CLAIMS = ["sub", "id", "purpose", "iss", "aud", "iat", "exp", "jti"]


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
                amr=payload.get("amr") or [],
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
