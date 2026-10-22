"""Email addresses at rest: AES-256-GCM to store them, a keyed hash to find them."""

import base64
import binascii
import hashlib
import hmac
import os
from collections.abc import Iterable
from typing import ClassVar, Self

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import SecretStr

from settings import Settings, get_settings


class EmailCipherError(RuntimeError):
    """A stored address cannot be read, or a key is missing or malformed."""


class EmailCipher:
    """
    Encrypts the address a row stores, and computes the hash that finds it.

    - Stored form: ``e1.<key id>.<nonce + ciphertext + tag, base64url>``. The
      nonce is random on every write, so one address encrypts differently each
      time and the column says nothing about which rows share an address.
    - The key id (the first 8 hex digits of the key's SHA-256) names the key
      that wrote a value. After a rotation the new key encrypts, and the old
      ones, kept in EMAIL_ENCRYPTION_OLD_KEYS, still decrypt what they wrote.
    - Lookup: HMAC-SHA256 of the trimmed, lower-cased address under a key of
      its own. It is deterministic, so an equality query can find the row,
      and keyed, so nobody without the key can hash a list of known addresses
      and match them against the table.

    Keys are 32 random bytes, base64-encoded, in the service's Vault path.
    """

    SCHEME = "e1"
    KEY_BYTES = 32
    NONCE_BYTES = 12

    _current: ClassVar["EmailCipher | None"] = None

    def __init__(self, key: bytes, old_keys: Iterable[bytes] = (), lookup_key: bytes | None = None) -> None:
        self._key_id = self._key_id_of(key)
        # The current key last, so it wins should an old key repeat it.
        self._keys = {self._key_id_of(old): AESGCM(old) for old in old_keys}
        self._keys[self._key_id] = AESGCM(key)
        self._lookup_key = lookup_key

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        old_keys = settings.EMAIL_ENCRYPTION_OLD_KEYS.get_secret_value() if settings.EMAIL_ENCRYPTION_OLD_KEYS else ""
        return cls(
            key=cls._decode_key(settings.EMAIL_ENCRYPTION_KEY, "EMAIL_ENCRYPTION_KEY"),
            old_keys=[cls._decode_key(part, "EMAIL_ENCRYPTION_OLD_KEYS") for part in old_keys.split(",") if part.strip()],
            lookup_key=(
                cls._decode_key(settings.EMAIL_LOOKUP_KEY, "EMAIL_LOOKUP_KEY")
                if settings.EMAIL_LOOKUP_KEY is not None else None
            ),
        )

    @classmethod
    def current(cls) -> "EmailCipher":
        """The process's cipher, built from its settings on first use."""
        if cls._current is None:
            cls._current = cls.from_settings(get_settings())
        return cls._current

    @classmethod
    def is_encrypted(cls, stored: str) -> bool:
        return stored.startswith(f"{cls.SCHEME}.")

    def encrypt(self, email: str) -> str:
        nonce = os.urandom(self.NONCE_BYTES)
        sealed = self._keys[self._key_id].encrypt(nonce, email.encode("utf-8"), self.SCHEME.encode())
        body = base64.urlsafe_b64encode(nonce + sealed).rstrip(b"=").decode("ascii")
        return f"{self.SCHEME}.{self._key_id}.{body}"

    def decrypt(self, stored: str) -> str:
        scheme, _, rest = stored.partition(".")
        key_id, _, body = rest.partition(".")
        if scheme != self.SCHEME or not body:
            # Never the value itself: it may be a plain-text address.
            raise EmailCipherError("Stored email is not in the encrypted form")
        aead = self._keys.get(key_id)
        if aead is None:
            raise EmailCipherError(
                f"Stored email was encrypted with key {key_id}, which is neither "
                "EMAIL_ENCRYPTION_KEY nor one of EMAIL_ENCRYPTION_OLD_KEYS"
            )
        try:
            raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
            plain = aead.decrypt(raw[: self.NONCE_BYTES], raw[self.NONCE_BYTES :], self.SCHEME.encode())
        except (InvalidTag, ValueError, binascii.Error) as error:
            raise EmailCipherError(f"Stored email under key {key_id} failed to decrypt") from error
        return plain.decode("utf-8")

    def lookup_hash(self, email: str) -> str:
        if self._lookup_key is None:
            raise EmailCipherError(
                "EMAIL_LOOKUP_KEY is not configured for this service; put it in this "
                "service's Vault path (secret/ecommerce/<service>)"
            )
        normalised = email.strip().lower().encode("utf-8")
        return hmac.new(self._lookup_key, normalised, hashlib.sha256).hexdigest()

    @staticmethod
    def _key_id_of(key: bytes) -> str:
        return hashlib.sha256(key).hexdigest()[:8]

    @classmethod
    def _decode_key(cls, value: SecretStr | str, name: str) -> bytes:
        text = value.get_secret_value() if isinstance(value, SecretStr) else value
        try:
            key = base64.b64decode(text.strip(), validate=True)
        except binascii.Error as error:
            raise EmailCipherError(f"{name} is not base64") from error
        if len(key) != cls.KEY_BYTES:
            raise EmailCipherError(f"{name} must be {cls.KEY_BYTES} bytes, base64-encoded")
        return key
