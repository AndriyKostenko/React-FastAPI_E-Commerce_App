"""Cross-service record of which access tokens have been revoked."""

from uuid import UUID

from shared.managers.redis_base import RedisBase


class SessionRegistry(RedisBase):
    """Publishes and checks the current session generation for a user.

    Access tokens carry a ``ver`` claim taken from the user's ``token_version``.
    Bumping that column — on password reset, on account deletion — is what a
    "log me out everywhere" action does. But only user-service can see the
    column, while the API gateway is what authenticates every other request,
    so without a shared record the gateway keeps honouring tokens the user has
    already revoked until they expire on their own.

    This registry is that record. user-service writes the new generation the
    moment it bumps; the gateway reads it on each authenticated request and
    refuses a token from an older generation.

    A missing entry means "nothing has ever been revoked for this user", so it
    is accepted: failing closed would invalidate every live session the first
    time this ships, and the entry outlives the longest refresh token anyway.
    """

    # Held longer than the longest-lived token that could still reference an
    # older generation; past that, expiry alone has already ended the session.
    DEFAULT_TTL_SECONDS: int = 8 * 24 * 3600

    def _key(self, user_id: UUID | str) -> str:
        return f"session:generation:{user_id}"

    async def publish_generation(
        self,
        user_id: UUID | str,
        token_version: int,
        ttl_seconds: int | None = None,
    ) -> None:
        """Record the generation that tokens must now carry to be accepted."""
        try:
            await self.redis.setex(
                name=self._key(user_id),
                time=ttl_seconds or self.DEFAULT_TTL_SECONDS,
                value=str(int(token_version)),
            )
            self.logger.info(
                "Session generation for user %s advanced to %s", user_id, token_version
            )
        except Exception as error:
            # A failure here leaves the old generation in place, which only
            # delays revocation until the token expires. Losing the request
            # that triggered it would be worse.
            self.logger.error(
                "Could not publish session generation for user %s: %s", user_id, error
            )

    async def current_generation(self, user_id: UUID | str) -> int | None:
        """The generation tokens must carry, or None when nothing is recorded."""
        try:
            raw = await self.redis.get(self._key(user_id))
        except Exception as error:
            # Redis is unavailable: fall back to the token's own short expiry
            # rather than locking every user out of the site.
            self.logger.error(
                "Could not read session generation for user %s: %s", user_id, error
            )
            return None
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            self.logger.error("Corrupt session generation for user %s: %r", user_id, raw)
            return None

    async def is_revoked(self, user_id: UUID | str, token_version: int | None) -> bool:
        """True when this token predates the user's current session generation."""
        current = await self.current_generation(user_id)
        if current is None:
            return False
        if token_version is None:
            # A token minted before versioning existed cannot be placed in the
            # sequence, and the user has since revoked something.
            return True
        return int(token_version) < current
