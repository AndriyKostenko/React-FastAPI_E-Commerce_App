"""
Google ID-token verification with real RS256 signatures.

A locally generated RSA key plays Google's signing key; its public half is
seeded into the service's JWKS cache, so the test needs no network but every
signature, audience, issuer and expiry check runs for real.
"""

from collections.abc import Iterator
from time import monotonic, time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, generate_private_key
from fastapi import HTTPException
from jwt.algorithms import RSAAlgorithm
from orjson import loads

from service_layer.user_service import UserService


KID = "test-google-key"


@pytest.fixture(scope="module")
def google_key() -> RSAPrivateKey:
    return generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def seeded_jwks(google_key: RSAPrivateKey) -> Iterator[None]:
    jwk = loads(RSAAlgorithm.to_jwk(google_key.public_key())) | {"kid": KID, "alg": "RS256", "use": "sig"}
    previous = (UserService._google_jwks, UserService._google_jwks_expires_at)
    UserService._google_jwks = {"keys": [jwk]}
    UserService._google_jwks_expires_at = monotonic() + 600
    yield
    UserService._google_jwks, UserService._google_jwks_expires_at = previous


def _id_token(key: RSAPrivateKey, audience: str, **overrides: object) -> str:
    claims: dict[str, object] = {
        "iss": "https://accounts.google.com",
        "aud": audience,
        "sub": "google-user-1",
        "email": "someone@example.com",
        "email_verified": True,
        "iat": int(time()),
        "exp": int(time()) + 600,
    } | overrides
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": KID})


@pytest.mark.usefixtures("seeded_jwks")
class TestVerifyGoogleIdToken:
    async def test_accepts_a_valid_token(self, user_service: UserService, google_key: RSAPrivateKey) -> None:
        audience = user_service.settings.GOOGLE_CLIENT_ID
        claims = await user_service._verify_google_id_token(_id_token(google_key, audience))
        assert claims["email"] == "someone@example.com"

    async def test_accepts_the_bare_issuer_form(self, user_service: UserService, google_key: RSAPrivateKey) -> None:
        token = _id_token(google_key, user_service.settings.GOOGLE_CLIENT_ID, iss="accounts.google.com")
        assert (await user_service._verify_google_id_token(token))["sub"] == "google-user-1"

    @pytest.mark.parametrize(
        "overrides",
        [
            {"aud": "some-other-client"},
            {"iss": "https://evil.example.com"},
            {"exp": int(time()) - 60},
        ],
        ids=["wrong-audience", "wrong-issuer", "expired"],
    )
    async def test_rejects_a_token_failing_a_claim_check(
        self, user_service: UserService, google_key: RSAPrivateKey, overrides: dict[str, object]
    ) -> None:
        token = _id_token(google_key, user_service.settings.GOOGLE_CLIENT_ID, **overrides)
        with pytest.raises(HTTPException) as exc_info:
            await user_service._verify_google_id_token(token)
        assert exc_info.value.status_code == 401

    async def test_rejects_a_token_signed_by_another_key(self, user_service: UserService) -> None:
        impostor = generate_private_key(public_exponent=65537, key_size=2048)
        with pytest.raises(HTTPException):
            await user_service._verify_google_id_token(
                _id_token(impostor, user_service.settings.GOOGLE_CLIENT_ID)
            )

    async def test_rejects_a_symmetric_token(self, user_service: UserService) -> None:
        # alg confusion: an HS256 token must not be checked with the RSA key.
        token = jwt.encode(
            {"aud": user_service.settings.GOOGLE_CLIENT_ID, "iss": "https://accounts.google.com"},
            "shared-secret",
            algorithm="HS256",
            headers={"kid": KID},
        )
        with pytest.raises(HTTPException):
            await user_service._verify_google_id_token(token)
