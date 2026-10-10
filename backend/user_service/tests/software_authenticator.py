"""
A software passkey authenticator for tests: real keys, real signatures.

It does what a platform authenticator does for ``navigator.credentials``:
holds a P-256 key pair, builds authenticator data and an attestation object,
and signs ``authenticatorData || SHA-256(clientDataJSON)`` with ES256. Nothing
in the server's verification is stubbed: py_webauthn checks every byte, so a
test that passes here passes for the same reasons a real sign-in does.

The knobs (``user_verified``, ``origin``, sign counter) exist so tests can
produce exactly the faulty responses a hostile or broken client would.
"""

import hashlib
import json
import secrets
import struct
from dataclasses import dataclass, field

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, encode_cbor

# Authenticator data flags (WebAuthn §6.1).
_USER_PRESENT = 0x01
_USER_VERIFIED = 0x04
_ATTESTED_CREDENTIAL_DATA = 0x40

type CredentialJson = dict[str, str | dict[str, str | list[str]] | list[str]]


@dataclass
class SoftwareAuthenticator:
    rp_id: str
    origin: str
    credential_id: bytes = field(default_factory=lambda: secrets.token_bytes(32))
    private_key: ec.EllipticCurvePrivateKey = field(default_factory=lambda: ec.generate_private_key(ec.SECP256R1()))
    sign_count: int = 0
    aaguid: bytes = bytes(16)

    # ------------------------------ registration ---------------------------

    def create(self, options: dict[str, object], *, user_verified: bool = True, origin: str | None = None) -> CredentialJson:
        """Answer PublicKeyCredentialCreationOptions (JSON form) with a new credential."""
        client_data = self._client_data("webauthn.create", str(options["challenge"]), origin)
        flags = _USER_PRESENT | _ATTESTED_CREDENTIAL_DATA | (_USER_VERIFIED if user_verified else 0)
        attested = self.aaguid + struct.pack(">H", len(self.credential_id)) + self.credential_id + self._cose_public_key()
        auth_data = self._rp_id_hash() + bytes([flags]) + struct.pack(">I", self.sign_count) + attested
        attestation_object = encode_cbor({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": bytes_to_base64url(self.credential_id),
            "rawId": bytes_to_base64url(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "attestationObject": bytes_to_base64url(attestation_object),
                "transports": ["internal"],
            },
            "authenticatorAttachment": "platform",
        }

    # ----------------------------- authentication --------------------------

    def get(
        self,
        options: dict[str, object],
        *,
        user_verified: bool = True,
        origin: str | None = None,
        advance_counter: bool = True,
    ) -> CredentialJson:
        """Answer PublicKeyCredentialRequestOptions (JSON form) with a signed assertion."""
        if advance_counter:
            self.sign_count += 1
        client_data = self._client_data("webauthn.get", str(options["challenge"]), origin)
        flags = _USER_PRESENT | (_USER_VERIFIED if user_verified else 0)
        auth_data = self._rp_id_hash() + bytes([flags]) + struct.pack(">I", self.sign_count)
        signature = self.private_key.sign(
            auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256())
        )
        return {
            "id": bytes_to_base64url(self.credential_id),
            "rawId": bytes_to_base64url(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "authenticatorData": bytes_to_base64url(auth_data),
                "signature": bytes_to_base64url(signature),
            },
            "authenticatorAttachment": "platform",
        }

    # -------------------------------- helpers ------------------------------

    def _client_data(self, ceremony: str, challenge: str, origin: str | None) -> bytes:
        # The challenge is echoed exactly as the server sent it (base64url).
        base64url_to_bytes(challenge)  # fail loudly on a malformed challenge
        return json.dumps(
            {"type": ceremony, "challenge": challenge, "origin": origin or self.origin, "crossOrigin": False},
            separators=(",", ":"),
        ).encode("utf-8")

    def _rp_id_hash(self) -> bytes:
        return hashlib.sha256(self.rp_id.encode("utf-8")).digest()

    def _cose_public_key(self) -> bytes:
        numbers = self.private_key.public_key().public_numbers()
        # COSE_Key, EC2 / P-256 / ES256 (RFC 9053).
        return encode_cbor({
            1: 2,
            3: -7,
            -1: 1,
            -2: numbers.x.to_bytes(32, "big"),
            -3: numbers.y.to_bytes(32, "big"),
        })
