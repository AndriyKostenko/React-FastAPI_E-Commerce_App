"""user-service's token issuer, copied for the gateway's tests only.

The gateway never signs user tokens (it holds the public key alone), but its
tests check the middleware against real ones. Keep this in step with
user-service's ``infrastructure/auth/user_tokens.py``.
"""

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from infrastructure.auth.user_tokens import ALGORITHM, TokenPurpose


# Claims this module sets itself; a caller's extra claims may never replace them,
# or an "extra" {"purpose": "access"} would turn a refresh token into an access one.
_RESERVED_CLAIMS = frozenset({"sub", "id", "role", "purpose", "iss", "aud", "iat", "exp", "jti"})

type ClaimValue = str | int | float | bool | None | list[str]


class UserTokenIssuer:
    """
    Signs user tokens. Holds the private key, so only user-service builds one:
    no other process can mint a session, whatever else it is given.
    """

    def __init__(self, private_key: Ed25519PrivateKey, issuer: str, audience: str) -> None:
        self._private_key = private_key
        self._issuer = issuer
        self._audience = audience

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
