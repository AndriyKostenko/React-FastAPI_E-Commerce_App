"""
Unit tests for TokenManager.

Uses a minimal in-memory Settings substitute so the tests run
without a live environment or .env file.
"""
from datetime import timedelta
from uuid import UUID
from time import time

import pytest
from fastapi import HTTPException

from shared.managers.token_manager import TokenManager
from shared.shared_instances import test_settings


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

    def test_encodes_custom_purpose(self, token_manager: TokenManager) -> None:
        token, _ = token_manager.create_access_token(
            email=test_settings.TEST_EMAIL,
            user_id=test_settings.TEST_USER_ID,
            role=test_settings.TEST_USER_ROLE,
            expires_delta=timedelta(minutes=60),
            purpose="email_verification",
        )
        decoded = token_manager.decode_token(token, required_purpose="email_verification")
        assert decoded.purpose == "email_verification"


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
