import hashlib
import json
import secrets
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from shared.managers.cache_manager import CacheManager
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url


class CeremonyPurpose(StrEnum):
    SIGN_IN = "sign-in"
    ENROLMENT = "enrolment"


@dataclass(frozen=True, slots=True)
class PendingChallenge:
    """A challenge the server sent and has not yet seen answered."""

    purpose: CeremonyPurpose
    user_id: UUID
    challenge: bytes
    # For enrolment, the hash of the link token the options were made for: the
    # answer is accepted only together with that same token.
    binding: str | None


class PasskeyCeremonyStore:
    """Short-lived, single-use state of passkey ceremonies, kept in Redis.

    Two kinds of entry, both only ever read once:

    * enrolment link tokens — what the owner is handed to register a passkey
      for an admin; stored as a hash, so Redis never holds a usable link;
    * challenges — the random bytes an authenticator must sign. Taken with
      GETDEL, so a signed answer can be presented at most once (replay).
    """

    def __init__(self, cache: CacheManager, challenge_ttl_seconds: int, enrolment_ttl_seconds: int) -> None:
        self._cache = cache
        self._challenge_ttl = challenge_ttl_seconds
        self._enrolment_ttl = enrolment_ttl_seconds

    @staticmethod
    def token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _enrolment_key(token: str) -> str:
        return f"passkey:enrolment:{PasskeyCeremonyStore.token_hash(token)}"

    @staticmethod
    def _challenge_key(challenge_id: str) -> str:
        return f"passkey:challenge:{challenge_id}"

    @staticmethod
    def _text(value: bytes | str | None) -> str | None:
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else value

    # ------------------------------ enrolment ------------------------------

    async def issue_enrolment_token(self, user_id: UUID) -> str:
        token = secrets.token_urlsafe(32)
        await self._cache.redis.setex(self._enrolment_key(token), self._enrolment_ttl, str(user_id))
        return token

    async def enrolment_user(self, token: str) -> UUID | None:
        """Whose link this is, without spending it (the options step)."""
        user_id = self._text(await self._cache.redis.get(self._enrolment_key(token)))
        return UUID(user_id) if user_id else None

    async def consume_enrolment_token(self, token: str) -> UUID | None:
        """Spend the link: only once a passkey has actually been registered with it."""
        user_id = self._text(await self._cache.redis.getdel(self._enrolment_key(token)))
        return UUID(user_id) if user_id else None

    # ------------------------------ challenges -----------------------------

    async def open_challenge(
        self,
        purpose: CeremonyPurpose,
        user_id: UUID,
        challenge: bytes,
        binding: str | None = None,
    ) -> str:
        challenge_id = secrets.token_urlsafe(24)
        payload = {
            "purpose": purpose.value,
            "user_id": str(user_id),
            "challenge": bytes_to_base64url(challenge),
            "binding": binding,
        }
        await self._cache.redis.setex(self._challenge_key(challenge_id), self._challenge_ttl, json.dumps(payload))
        return challenge_id

    async def take_challenge(self, challenge_id: str, purpose: CeremonyPurpose) -> PendingChallenge | None:
        """The pending challenge, removed as it is read; None if unknown, used or expired."""
        raw = self._text(await self._cache.redis.getdel(self._challenge_key(challenge_id)))
        if raw is None:
            return None
        payload = json.loads(raw)
        # A sign-in challenge must never complete an enrolment, or the reverse.
        if payload["purpose"] != purpose.value:
            return None
        return PendingChallenge(
            purpose=purpose,
            user_id=UUID(payload["user_id"]),
            challenge=base64url_to_bytes(payload["challenge"]),
            binding=payload["binding"],
        )
