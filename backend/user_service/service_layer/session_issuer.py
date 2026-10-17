import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from models.user_models import User
from contracts.auth import AuthMethod
from infrastructure.managers.cache_manager import CacheManager
from infrastructure.managers.token_manager import TokenManager
from settings import Settings


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

    @staticmethod
    def signed_out_key(token_hash: str) -> str:
        """Marks a refresh token ended by a sign-out, as opposed to spent by a refresh."""
        return f"refresh:signed_out:{token_hash}"

    @staticmethod
    def rotated_key(token_hash: str) -> str:
        """Points from a spent refresh token to the one its refresh issued."""
        return f"refresh:rotated:{token_hash}"

    @property
    def refresh_ttl_seconds(self) -> int:
        """How long a refresh token lives, and so how long anything about it is kept."""
        return self._settings.REFRESH_TOKEN_TIME_DELTA_DAYS * 86400

    async def issue(
        self, user: User, methods: Sequence[AuthMethod], rotated_from: str | None = None
    ) -> IssuedSession:
        """Mint a pair; ``rotated_from`` is the hash of the refresh token this one replaces."""
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
        await self._store_refresh(user.id, refresh_token, rotated_from)
        return IssuedSession(access_token, access_expiry, refresh_token, refresh_expiry)

    async def _store_refresh(self, user_id: UUID, refresh_token: str, rotated_from: str | None) -> None:
        """Store the hashed refresh token and index it in the user's active set.

        On a refresh, the spent token is also linked to the new one, in the same
        pipeline, so a sign-out that arrives with the spent token (it raced the
        refresh) can still find and end the token that replaced it. The link
        lives as long as the new token: after that there is nothing to end.
        """
        token_hash = self.token_hash(refresh_token)
        ttl_seconds = self.refresh_ttl_seconds
        pipe = self._cache.redis.pipeline()
        pipe.setex(self.refresh_key(token_hash), ttl_seconds, str(user_id))
        pipe.sadd(self.user_refresh_set_key(user_id), token_hash)
        pipe.expire(self.user_refresh_set_key(user_id), ttl_seconds)
        if rotated_from is not None:
            pipe.setex(self.rotated_key(rotated_from), ttl_seconds, token_hash)
        await pipe.execute()
