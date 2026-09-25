from collections.abc import Mapping
from datetime import timedelta
from typing import Self
from uuid import UUID

from pydantic import EmailStr

from shared.auth.user_tokens import (
    ClaimValue,
    TokenPurpose,
    UserTokenIssuer,
    UserTokenVerifier,
)
from shared.contracts.auth import TokenClaims
from shared.settings import Settings


class TokenManager:
    """
    Issues and verifies user tokens — user-service's view of them.

    A facade over ``UserTokenIssuer`` (private key) and ``UserTokenVerifier``
    (public key). Only user-service builds one, because only it holds the
    private key; the gateway builds a bare ``UserTokenVerifier`` instead.
    """

    def __init__(self, settings: Settings, issuer: UserTokenIssuer, verifier: UserTokenVerifier) -> None:
        self.settings = settings
        self._issuer = issuer
        self._verifier = verifier

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        return cls(
            settings=settings,
            issuer=UserTokenIssuer.from_settings(settings),
            verifier=UserTokenVerifier.from_settings(settings),
        )

    def create_access_token(
        self,
        email: EmailStr,
        user_id: UUID,
        role: str | None,
        expires_delta: timedelta,
        purpose: TokenPurpose | str = TokenPurpose.ACCESS,
        extra_claims: Mapping[str, ClaimValue] | None = None,
    ) -> tuple[str, int]:
        """Returns ``(token, expire_timestamp)``."""
        return self._issuer.issue(
            email=str(email),
            user_id=user_id,
            role=role,
            purpose=TokenPurpose(purpose),
            expires_delta=expires_delta,
            extra_claims=extra_claims,
        )

    def create_refresh_token(
        self,
        email: EmailStr,
        user_id: UUID,
        role: str | None,
        extra_claims: Mapping[str, ClaimValue] | None = None,
    ) -> tuple[str, int]:
        """A long-lived token (``purpose="refresh"``) whose hash is kept in Redis."""
        return self.create_access_token(
            email=email,
            user_id=user_id,
            role=role,
            expires_delta=timedelta(days=self.settings.REFRESH_TOKEN_TIME_DELTA_DAYS),
            purpose=TokenPurpose.REFRESH,
            extra_claims=extra_claims,
        )

    def decode_token(self, token: str, required_purpose: TokenPurpose | str = TokenPurpose.ACCESS) -> TokenClaims:
        """Raises ``HTTPException(401)`` if the token is invalid or has the wrong purpose."""
        return self._verifier.decode(token, TokenPurpose(required_purpose))

    def validate_token(self, token: str, required_purpose: TokenPurpose | str = TokenPurpose.ACCESS) -> bool:
        return self._verifier.is_valid(token, TokenPurpose(required_purpose))
