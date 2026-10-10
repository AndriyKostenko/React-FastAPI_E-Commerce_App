import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from models.user_models import User
from shared.contracts.auth import AuthMethod
from shared.managers.cache_manager import CacheManager
from shared.managers.token_manager import TokenManager
from shared.settings import Settings


@dataclass(frozen=True, slots=True)
class IssuedSession:
    access_token: str
    access_expiry: int
    refresh_token: str
    refresh_expiry: int


class SessionIssuer:
    """Mints a user's access + refresh pair: the one place a session starts.

    Every sign-in (password, Google, passkey) and every refresh ends here, so
    the claims a session carries cannot drift between them. ``amr`` records how
    the session was signed in and is copied unchanged into each refreshed pair:
    the gateway refuses an admin token whose session never presented a passkey.
    """

    def __init__(self, token_manager: TokenManager, cache_manager: CacheManager, settings: Settings) -> None:
        self._tokens = token_manager
        self._cache = cache_manager
        self._settings = settings

    @staticmethod
    def token_hash(token: str) -> str:
        """SHA-256 of a token: what Redis keeps instead of the token itself."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def refresh_key(token_or_hash: str) -> str:
        return f"refresh:{token_or_hash}"

    @staticmethod
    def user_refresh_set_key(user_id: UUID | str) -> str:
        return f"refresh:user:{user_id}"

    async def issue(self, user: User, methods: Sequence[AuthMethod]) -> IssuedSession:
        claims: dict[str, int | list[str]] = {
            "ver": user.token_version,
            "amr": [method.value for method in methods],
        }
        access_token, access_expiry = self._tokens.create_access_token(
            email=user.email,
            user_id=user.id,
            role=user.role,
            expires_delta=timedelta(minutes=self._settings.TOKEN_TIME_DELTA_MINUTES),
            purpose="access",
            extra_claims=claims,
        )
        refresh_token, refresh_expiry = self._tokens.create_refresh_token(
            email=user.email,
            user_id=user.id,
            role=user.role,
            extra_claims=claims,
        )
        await self._store_refresh(user.id, refresh_token)
        return IssuedSession(access_token, access_expiry, refresh_token, refresh_expiry)

    async def _store_refresh(self, user_id: UUID, refresh_token: str) -> None:
        """Store the hashed refresh token and index it in the user's active set."""
        token_hash = self.token_hash(refresh_token)
        ttl_seconds = self._settings.REFRESH_TOKEN_TIME_DELTA_DAYS * 86400
        pipe = self._cache.redis.pipeline()
        pipe.setex(self.refresh_key(token_hash), ttl_seconds, str(user_id))
        pipe.sadd(self.user_refresh_set_key(user_id), token_hash)
        pipe.expire(self.user_refresh_set_key(user_id), ttl_seconds)
        await pipe.execute()
