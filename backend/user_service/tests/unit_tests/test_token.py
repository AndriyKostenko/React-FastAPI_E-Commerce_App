"""
Unit tests for TokenManager.

Uses a minimal in-memory Settings substitute so the tests run
without a live environment or .env file.
"""
from datetime import timedelta
from time import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException

from shared.managers.token_manager import TokenManager
from shared.settings import get_test_settings
from shared.testing.signing_keys import TEST_TOKEN_AUDIENCE, TEST_TOKEN_ISSUER, EphemeralSigningKeys

test_settings = get_test_settings()


class TestCreateAccessToken:
    def test_returns_non_empty_token_string(self, token_manager: TokenManager) -> None:
        token, expiry = token_manager.create_access_token(
            email=test_settings.TEST_EMAIL,
            user_id=test_settings.TEST_USER_ID,
            role=test_settings.TEST_USER_ROLE,
            expires_delta=timedelta(minutes=30),
        )
        assert isinstance(token, str) and len(token) > 0
        assert isinstance(expiry, int) and expiry > 0

    def test_encodes_email_and_role_in_payload(self, token_manager: TokenManager) -> None:
        token, _ = token_manager.create_access_token(
            email=test_settings.TEST_EMAIL,
            user_id=test_settings.TEST_USER_ID,
            role=test_settings.TEST_USER_ROLE,
            expires_delta=timedelta(minutes=30),
        )
        decoded = token_manager.decode_token(token)

        assert decoded.email == test_settings.TEST_EMAIL
        assert decoded.role == test_settings.TEST_USER_ROLE

    def test_defaults_purpose_to_access(self, token_manager: TokenManager) -> None:
        token, _ = token_manager.create_access_token(
            email=test_settings.TEST_EMAIL,
            user_id=test_settings.TEST_USER_ID,
            role=test_settings.TEST_USER_ROLE,
            expires_delta=timedelta(minutes=30),
        )
        decoded = token_manager.decode_token(token, required_purpose="access")
        assert decoded.purpose == "access"
        assert decoded.purpose != "wrong"

    def test_rejects_unknown_purpose(self, token_manager: TokenManager) -> None:
        # Only access and refresh tokens are JWTs; email verification and
        # password reset use random single-use tokens kept in Redis.
        with pytest.raises(ValueError):
            token_manager.create_access_token(
                email=test_settings.TEST_EMAIL,
                user_id=test_settings.TEST_USER_ID,
                role=test_settings.TEST_USER_ROLE,
                expires_delta=timedelta(minutes=60),
                purpose="email_verification",
            )


class TestCreateRefreshToken:
    def test_creates_token_with_refresh_purpose(self, token_manager: TokenManager) -> None:
        token, _ = token_manager.create_refresh_token(
            email=test_settings.TEST_EMAIL,
            user_id=test_settings.TEST_USER_ID,
            role=test_settings.TEST_USER_ROLE,
        )
        decoded = token_manager.decode_token(token, required_purpose="refresh")
        assert decoded.purpose == "refresh"
        assert decoded.email == test_settings.TEST_EMAIL

    def test_returns_valid_expiry_timestamp(self, token_manager: TokenManager) -> None:
        _, expiry = token_manager.create_refresh_token(
            email=test_settings.TEST_EMAIL,
            user_id=test_settings.TEST_USER_ID,
            role=test_settings.TEST_USER_ROLE,
        )

        assert expiry > int(time())


class TestDecodeToken:
    def test_round_trips_all_standard_fields(self, token_manager: TokenManager) -> None:
        token, _ = token_manager.create_access_token(
            email=test_settings.TEST_EMAIL,
            user_id=test_settings.TEST_USER_ID,
            role=test_settings.TEST_USER_ROLE,
            expires_delta=timedelta(minutes=30),
        )
        result = token_manager.decode_token(token)

        assert result.email == test_settings.TEST_EMAIL
        assert result.role == test_settings.TEST_USER_ROLE
        assert str(result.id) == str(test_settings.TEST_USER_ID)

    def test_raises_401_on_tampered_token(self, token_manager: TokenManager) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _ = token_manager.decode_token("tampered.invalid.jwt")
        assert exc_info.value.status_code == 401

    def test_raises_401_on_purpose_mismatch(self, token_manager: TokenManager) -> None:
        token, _ = token_manager.create_access_token(
            email=test_settings.TEST_EMAIL,
            user_id=test_settings.TEST_USER_ID,
            role=test_settings.TEST_USER_ROLE,
            expires_delta=timedelta(minutes=30),
            purpose="access",
        )

        with pytest.raises(HTTPException) as exc_info:
            _ = token_manager.decode_token(token, required_purpose="refresh")

        assert exc_info.value.status_code == 401
        assert "Invalid token purpose" in exc_info.value.detail

    def test_raises_401_on_expired_token(self, token_manager: TokenManager) -> None:
        token, _ = token_manager.create_access_token(
            email=test_settings.TEST_EMAIL,
            user_id=test_settings.TEST_USER_ID,
            role=test_settings.TEST_USER_ROLE,
            expires_delta=timedelta(seconds=-1),  # already expired
        )

        with pytest.raises(HTTPException) as exc_info:
            _ = token_manager.decode_token(token)

        assert exc_info.value.status_code == 401


class TestValidateToken:
    def test_returns_true_for_valid_token(self, token_manager: TokenManager) -> None:
        token, _ = token_manager.create_access_token(
            email=test_settings.TEST_EMAIL,
            user_id=test_settings.TEST_USER_ID,
            role=test_settings.TEST_USER_ROLE,
            expires_delta=timedelta(minutes=30),
        )
        assert token_manager.validate_token(token) is True

    def test_returns_false_for_garbage_token(self, token_manager: TokenManager) -> None:
        assert token_manager.validate_token("not.a.valid.token") is False

    def test_returns_false_on_purpose_mismatch(self, token_manager: TokenManager) -> None:
        token, _ = token_manager.create_access_token(
            email=test_settings.TEST_EMAIL,
            user_id=test_settings.TEST_USER_ID,
            role=test_settings.TEST_USER_ROLE,
            expires_delta=timedelta(minutes=30),
            purpose="access",
        )
        assert token_manager.validate_token(token, required_purpose="refresh") is False


class TestSigningSecurity:
    """What moving to Ed25519 is for: only the private-key holder can mint a session."""

    def _claims(self) -> dict[str, object]:
        return {
            "sub": test_settings.TEST_EMAIL,
            "id": str(test_settings.TEST_USER_ID),
            "role": test_settings.TEST_ADMIN_ROLE,
            "purpose": "access",
            "iss": TEST_TOKEN_ISSUER,
            "aud": TEST_TOKEN_AUDIENCE,
            "iat": int(time()),
            "exp": int(time()) + 600,
            "jti": "forged",
        }

    def test_rejects_token_signed_by_another_ed25519_key(self, token_manager: TokenManager) -> None:
        forged = jwt.encode(self._claims(), Ed25519PrivateKey.generate(), algorithm="EdDSA")
        with pytest.raises(HTTPException) as exc_info:
            token_manager.decode_token(forged)
        assert exc_info.value.status_code == 401

    def test_rejects_legacy_hs256_token_signed_with_the_shared_secret(self, token_manager: TokenManager) -> None:
        # The hard cutover: a token minted the old way, by anyone who held
        # SECRET_KEY, must no longer open a session.
        legacy = jwt.encode(self._claims(), test_settings.SECRET_KEY, algorithm="HS256")
        with pytest.raises(HTTPException):
            token_manager.decode_token(legacy)

    def test_rejects_unsigned_alg_none_token(self, token_manager: TokenManager) -> None:
        unsigned = jwt.encode(self._claims(), key=None, algorithm="none")
        with pytest.raises(HTTPException):
            token_manager.decode_token(unsigned)

    @pytest.mark.parametrize(("claim", "value"), [("iss", "someone-else"), ("aud", "another-api")])
    def test_rejects_wrong_issuer_or_audience(self, claim: str, value: str) -> None:
        keys = EphemeralSigningKeys()
        claims = self._claims() | {claim: value}
        token = jwt.encode(claims, keys.user_token_private_key, algorithm="EdDSA")
        with pytest.raises(HTTPException):
            keys.token_manager(test_settings).decode_token(token)

    def test_rejects_token_missing_a_required_claim(self) -> None:
        keys = EphemeralSigningKeys()
        claims = self._claims()
        del claims["jti"]
        token = jwt.encode(claims, keys.user_token_private_key, algorithm="EdDSA")
        with pytest.raises(HTTPException):
            keys.token_manager(test_settings).decode_token(token)

    def test_extra_claims_cannot_override_reserved_ones(self, token_manager: TokenManager) -> None:
        # Otherwise extra_claims={"purpose": "access"} would turn a refresh token into an access token.
        with pytest.raises(ValueError):
            token_manager.create_refresh_token(
                email=test_settings.TEST_EMAIL,
                user_id=test_settings.TEST_USER_ID,
                role=test_settings.TEST_USER_ROLE,
                extra_claims={"purpose": "access"},
            )

    def test_token_version_claim_round_trips(self, token_manager: TokenManager) -> None:
        token, _ = token_manager.create_refresh_token(
            email=test_settings.TEST_EMAIL,
            user_id=test_settings.TEST_USER_ID,
            role=test_settings.TEST_USER_ROLE,
            extra_claims={"ver": 7},
        )
        assert token_manager.decode_token(token, required_purpose="refresh").token_version == 7

    def test_two_tokens_issued_in_the_same_second_differ(self, token_manager: TokenManager) -> None:
        # Refresh tokens are stored by hash; identical tokens would share a Redis key.
        first, _ = token_manager.create_refresh_token(
            email=test_settings.TEST_EMAIL, user_id=test_settings.TEST_USER_ID, role=None
        )
        second, _ = token_manager.create_refresh_token(
            email=test_settings.TEST_EMAIL, user_id=test_settings.TEST_USER_ID, role=None
        )
        assert first != second
