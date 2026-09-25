"""Loads the Ed25519 keys that sign user tokens and gateway caller assertions."""

from base64 import b64decode
from binascii import Error as Base64Error

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    load_der_private_key,
    load_der_public_key,
    load_pem_private_key,
    load_pem_public_key,
)


class SigningKeyError(ValueError):
    """A configured key is malformed or is not an Ed25519 key."""


class Ed25519KeyLoader:
    """
    Accepts a key either as full PEM or as the bare base64 body of one (the
    DER inside the PEM armour) — the one-line form is what fits in an env file.
    A literal ``\\n`` is turned back into a newline, since that is how a
    multi-line PEM often survives a trip through an environment variable.
    """

    @classmethod
    def private_key(cls, encoded: str, name: str) -> Ed25519PrivateKey:
        # Decoded outside the try: an empty or non-base64 value already raises
        # a precise SigningKeyError, which must not be reworded as unreadable.
        is_pem = cls._is_pem(encoded)
        data = cls._pem_bytes(encoded) if is_pem else cls._der_bytes(encoded, name)
        try:
            key = (
                load_pem_private_key(data, password=None)
                if is_pem
                else load_der_private_key(data, password=None)
            )
        except (ValueError, TypeError) as error:
            raise SigningKeyError(f"{name} is not a readable private key") from error
        if not isinstance(key, Ed25519PrivateKey):
            raise SigningKeyError(f"{name} must be an Ed25519 key")
        return key

    @classmethod
    def public_key(cls, encoded: str, name: str) -> Ed25519PublicKey:
        is_pem = cls._is_pem(encoded)
        data = cls._pem_bytes(encoded) if is_pem else cls._der_bytes(encoded, name)
        try:
            key = load_pem_public_key(data) if is_pem else load_der_public_key(data)
        except (ValueError, TypeError) as error:
            raise SigningKeyError(f"{name} is not a readable public key") from error
        if not isinstance(key, Ed25519PublicKey):
            raise SigningKeyError(f"{name} must be an Ed25519 key")
        return key

    @staticmethod
    def _is_pem(encoded: str) -> bool:
        return "-----BEGIN" in encoded

    @staticmethod
    def _pem_bytes(encoded: str) -> bytes:
        return encoded.strip().replace("\\n", "\n").encode("ascii")

    @staticmethod
    def _der_bytes(encoded: str, name: str) -> bytes:
        compact = "".join(encoded.replace("\\n", "").split())
        if not compact:
            raise SigningKeyError(f"{name} is empty")
        try:
            return b64decode(compact, validate=True)
        except Base64Error as error:
            raise SigningKeyError(f"{name} is neither PEM nor base64") from error
