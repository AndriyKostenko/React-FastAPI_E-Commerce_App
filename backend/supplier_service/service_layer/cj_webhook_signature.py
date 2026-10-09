"""Proof that a webhook push came from CJ: the ``sign`` header CJ computes over the body."""

import base64
import hashlib
import hmac


class InvalidCJWebhookSignature(Exception):
    """The push's ``sign`` header is missing or does not match its body."""


class CJWebhookSignature:
    """
    ``sign = Base64(HMAC-SHA256(key = openId as a string, message = raw body))``.

    Computed over the bytes exactly as received: CJ serialises with fastjson
    (keys in alphabetical order), and any parse-and-reserialise on the way in
    changes them, after which no genuine push would verify.
    """

    HEADER = "sign"

    def __init__(self, open_id: str) -> None:
        if not open_id:
            raise ValueError("CJ webhook signing needs the account's openId")
        self._key = open_id.encode("utf-8")

    def sign(self, body: bytes) -> str:
        digest = hmac.new(self._key, body, hashlib.sha256).digest()
        return base64.b64encode(digest).decode("ascii")

    def verify(self, body: bytes, signature: str | None) -> None:
        """Raise unless ``signature`` is CJ's signature of ``body``."""
        if not signature:
            raise InvalidCJWebhookSignature(f"no {self.HEADER} header")
        # Constant-time: a timing difference would leak the signature byte by
        # byte. Compared as bytes: compare_digest refuses non-ASCII str.
        expected = self.sign(body).encode("ascii")
        if not hmac.compare_digest(expected, signature.strip().encode("utf-8")):
            raise InvalidCJWebhookSignature("signature does not match the body")
