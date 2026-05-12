"""
Unit tests for UserService.

All external dependencies (repository, password manager, token manager,
Redis) are mocked so every test runs without a live database or cache.
Tests are grouped by service method using classes for readability.
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from exceptions.user_exceptions import (
    UserAlreadyExistsError,
    UserNotFoundError,
    UserUpdateError,
)
from shared.schemas.user_schemas import (
    DecodedTokenSchema,
    UserBasicUpdate,
    UserSignUp,
    UsersFilterParams,
)


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------


class TestCreateUser:
    async def test_creates_user_and_returns_verification_token(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_token_manager: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = None
        mock_repository.create.return_value = mock_user_orm
        mock_token_manager.create_access_token.return_value = ("verify_tok", 9999)

        data = UserSignUp(name="Test User", email="test@example.com", password="password123")
        user_info, token = await user_service.create_user(data)

        assert user_info.email == "test@example.com"
        assert token == "verify_tok"
        mock_repository.get_by_field.assert_awaited_once_with("email", data.email)
        mock_repository.create.assert_awaited_once()

    async def test_raises_when_email_already_registered(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = mock_user_orm

        data = UserSignUp(name="Test User", email="test@example.com", password="password123")
        with pytest.raises(UserAlreadyExistsError):
            await user_service.create_user(data)

    async def test_hashes_plain_password_before_saving(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_password_manager: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = None
        mock_repository.create.return_value = mock_user_orm

        data = UserSignUp(name="Test User", email="test@example.com", password="plain_pw")
        await user_service.create_user(data)

        mock_password_manager.hash_password.assert_called_once_with("plain_pw")


# ---------------------------------------------------------------------------
# verify_password
# ---------------------------------------------------------------------------


class TestVerifyPassword:
    async def test_returns_true_for_correct_credentials(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_password_manager: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = mock_user_orm
        mock_password_manager.verify_password.return_value = True

        result = await user_service.verify_password("test@example.com", "correct_pw")

        assert result is True

    async def test_returns_false_for_wrong_password(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_password_manager: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = mock_user_orm
        mock_password_manager.verify_password.return_value = False

        result = await user_service.verify_password("test@example.com", "wrong_pw")

        assert result is False

    async def test_raises_when_user_not_found(
        self,
        user_service,
        mock_repository: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = None

        with pytest.raises(UserNotFoundError):
            await user_service.verify_password("ghost@example.com", "any_pw")


# ---------------------------------------------------------------------------
# get_all_users
# ---------------------------------------------------------------------------


class TestGetAllUsers:
    async def test_returns_validated_user_list(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
    ) -> None:
        mock_repository.get_all.return_value = [mock_user_orm]

        result = await user_service.get_all_users(UsersFilterParams())

        assert len(result) == 1
        assert result[0].email == "test@example.com"

    async def test_raises_when_query_returns_no_users(
        self,
        user_service,
        mock_repository: MagicMock,
    ) -> None:
        mock_repository.get_all.return_value = []

        with pytest.raises(UserNotFoundError):
            await user_service.get_all_users(UsersFilterParams())


# ---------------------------------------------------------------------------
# get_user_by_email
# ---------------------------------------------------------------------------


class TestGetUserByEmail:
    async def test_returns_user_for_known_email(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = mock_user_orm

        result = await user_service.get_user_by_email("test@example.com")

        assert result.email == "test@example.com"
        mock_repository.get_by_field.assert_awaited_once_with(
            field_name="email", value="test@example.com"
        )

    async def test_raises_for_unknown_email(
        self,
        user_service,
        mock_repository: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = None

        with pytest.raises(UserNotFoundError):
            await user_service.get_user_by_email("ghost@example.com")


# ---------------------------------------------------------------------------
# get_user_by_id
# ---------------------------------------------------------------------------


class TestGetUserById:
    async def test_returns_user_for_known_id(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
    ) -> None:
        mock_repository.get_by_id.return_value = mock_user_orm

        result = await user_service.get_user_by_id(mock_user_orm.id)

        assert result.id == mock_user_orm.id

    async def test_raises_for_unknown_id(
        self,
        user_service,
        mock_repository: MagicMock,
    ) -> None:
        mock_repository.get_by_id.return_value = None

        with pytest.raises(UserNotFoundError):
            await user_service.get_user_by_id(uuid4())


# ---------------------------------------------------------------------------
# get_user_hashed_password
# ---------------------------------------------------------------------------


class TestGetUserHashedPassword:
    async def test_returns_hashed_password(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = mock_user_orm

        result = await user_service.get_user_hashed_password("test@example.com")

        assert result == mock_user_orm.hashed_password

    async def test_raises_when_user_not_found(
        self,
        user_service,
        mock_repository: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = None

        with pytest.raises(UserNotFoundError):
            await user_service.get_user_hashed_password("ghost@example.com")


# ---------------------------------------------------------------------------
# update_user_password
# ---------------------------------------------------------------------------


class TestUpdateUserPassword:
    async def test_hashes_and_persists_new_password(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_password_manager: MagicMock,
    ) -> None:
        mock_repository.update_by_field.return_value = mock_user_orm

        result = await user_service.update_user_password("test@example.com", "new_pw")

        assert result.email == "test@example.com"
        mock_password_manager.hash_password.assert_called_once_with("new_pw")

    async def test_raises_when_user_not_found(
        self,
        user_service,
        mock_repository: MagicMock,
    ) -> None:
        mock_repository.update_by_field.return_value = None

        with pytest.raises(UserNotFoundError):
            await user_service.update_user_password("ghost@example.com", "new_pw")


# ---------------------------------------------------------------------------
# update_user_basic_info
# ---------------------------------------------------------------------------


class TestUpdateUserBasicInfo:
    async def test_updates_and_returns_user(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
    ) -> None:
        mock_repository.update_by_id.return_value = mock_user_orm

        result = await user_service.update_user_basic_info(
            mock_user_orm.id, UserBasicUpdate(name="New Name")
        )

        assert result.email == "test@example.com"
        mock_repository.update_by_id.assert_awaited_once_with(
            item_id=mock_user_orm.id, data={"name": "New Name", "phone_number": None, "image": None}
        )

    async def test_raises_when_user_not_found(
        self,
        user_service,
        mock_repository: MagicMock,
    ) -> None:
        mock_repository.update_by_id.return_value = None

        with pytest.raises(UserNotFoundError):
            await user_service.update_user_basic_info(uuid4(), UserBasicUpdate(name="X"))


# ---------------------------------------------------------------------------
# verify_email
# ---------------------------------------------------------------------------


class TestVerifyEmail:
    async def test_marks_email_as_verified(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_token_manager: MagicMock,
    ) -> None:
        decoded = DecodedTokenSchema(
            email="test@example.com",
            id=mock_user_orm.id,
            role="user",
            purpose="email_verification",
        )
        mock_token_manager.decode_token.return_value = decoded
        mock_repository.update_by_field.return_value = mock_user_orm

        result = await user_service.verify_email("verification_token")

        assert result.email == "test@example.com"
        mock_token_manager.decode_token.assert_called_once_with(
            token="verification_token", required_purpose="email_verification"
        )
        mock_repository.update_by_field.assert_awaited_once_with(
            field_name="email", value="test@example.com", is_verified=True
        )

    async def test_raises_when_user_not_found_after_token_decode(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_token_manager: MagicMock,
    ) -> None:
        decoded = DecodedTokenSchema(
            email="test@example.com",
            id=mock_user_orm.id,
            role="user",
            purpose="email_verification",
        )
        mock_token_manager.decode_token.return_value = decoded
        mock_repository.update_by_field.return_value = None

        with pytest.raises(UserNotFoundError):
            await user_service.verify_email("verification_token")


# ---------------------------------------------------------------------------
# delete_user_by_id
# ---------------------------------------------------------------------------


class TestDeleteUserById:
    async def test_deletes_user_without_raising(
        self,
        user_service,
        mock_repository: MagicMock,
    ) -> None:
        mock_repository.delete_by_id.return_value = True
        await user_service.delete_user_by_id(uuid4())  # must not raise

    async def test_raises_when_user_not_found(
        self,
        user_service,
        mock_repository: MagicMock,
    ) -> None:
        mock_repository.delete_by_id.return_value = False

        with pytest.raises(UserNotFoundError):
            await user_service.delete_user_by_id(uuid4())


# ---------------------------------------------------------------------------
# get_verified_users
# ---------------------------------------------------------------------------


class TestGetVerifiedUsers:
    async def test_returns_verified_users(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
    ) -> None:
        mock_repository.get_verified_users.return_value = [mock_user_orm]

        result = await user_service.get_verified_users()

        assert len(result) == 1
        assert result[0].is_verified is True

    async def test_returns_empty_list_when_no_verified_users(
        self,
        user_service,
        mock_repository: MagicMock,
    ) -> None:
        mock_repository.get_verified_users.return_value = []

        result = await user_service.get_verified_users()

        assert result == []


# ---------------------------------------------------------------------------
# get_by_role
# ---------------------------------------------------------------------------


class TestGetByRole:
    async def test_returns_users_matching_role(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
    ) -> None:
        mock_repository.get_users_by_role.return_value = [mock_user_orm]

        result = await user_service.get_by_role("admin")

        assert len(result) == 1
        mock_repository.get_users_by_role.assert_awaited_once_with(role="admin")

    async def test_returns_empty_list_when_no_users_with_role(
        self,
        user_service,
        mock_repository: MagicMock,
    ) -> None:
        mock_repository.get_users_by_role.return_value = []

        result = await user_service.get_by_role("superadmin")

        assert result == []


# ---------------------------------------------------------------------------
# request_password_reset
# ---------------------------------------------------------------------------


class TestRequestPasswordReset:
    async def test_returns_user_and_reset_token(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_token_manager: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = mock_user_orm
        mock_token_manager.create_access_token.return_value = ("reset_tok", 9999)

        user, token = await user_service.request_password_reset("test@example.com")

        assert user.email == "test@example.com"
        assert token == "reset_tok"

    async def test_raises_when_user_not_found(
        self,
        user_service,
        mock_repository: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = None

        with pytest.raises(UserNotFoundError):
            await user_service.request_password_reset("ghost@example.com")


# ---------------------------------------------------------------------------
# reset_password_with_token
# ---------------------------------------------------------------------------


class TestResetPasswordWithToken:
    async def test_resets_password_successfully(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_token_manager: MagicMock,
        mock_password_manager: MagicMock,
    ) -> None:
        decoded = DecodedTokenSchema(
            email="test@example.com",
            id=mock_user_orm.id,
            role="user",
            purpose="password_reset",
        )
        mock_token_manager.decode_token.return_value = decoded
        mock_repository.update_by_field.return_value = mock_user_orm
        mock_password_manager.hash_password.return_value = "new_hashed_pw"

        result = await user_service.reset_password_with_token("reset_token", "new_pw123")

        assert result.email == "test@example.com"
        mock_password_manager.hash_password.assert_called_once_with("new_pw123")

    async def test_raises_when_db_update_fails(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_token_manager: MagicMock,
    ) -> None:
        decoded = DecodedTokenSchema(
            email="test@example.com",
            id=mock_user_orm.id,
            role="user",
            purpose="password_reset",
        )
        mock_token_manager.decode_token.return_value = decoded
        mock_repository.update_by_field.return_value = None

        with pytest.raises(UserUpdateError):
            await user_service.reset_password_with_token("reset_token", "new_pw123")


# ---------------------------------------------------------------------------
# authenticate_user
# ---------------------------------------------------------------------------


class TestAuthenticateUser:
    async def test_returns_user_and_tokens_for_valid_credentials(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_password_manager: MagicMock,
        mock_token_manager: MagicMock,
        mock_redis: AsyncMock,
    ) -> None:
        mock_repository.get_by_field.return_value = mock_user_orm
        mock_password_manager.verify_password.return_value = True
        mock_user_orm.is_verified = True
        mock_user_orm.is_active = True
        mock_token_manager.create_access_token.return_value = ("access_tok", 9999)
        mock_token_manager.create_refresh_token.return_value = ("refresh_tok", 9999)

        current_user, access_token, _, refresh_token, _ = await user_service.authenticate_user(
            "test@example.com", "correct_pw"
        )

        assert current_user.email == "test@example.com"
        assert access_token == "access_tok"
        assert refresh_token == "refresh_tok"
        mock_redis.setex.assert_awaited_once()

    async def test_raises_401_on_wrong_password(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_password_manager: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = mock_user_orm
        mock_password_manager.verify_password.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await user_service.authenticate_user("test@example.com", "wrong_pw")

        assert exc_info.value.status_code == 401

    async def test_raises_401_when_email_not_verified(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_password_manager: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = mock_user_orm
        mock_password_manager.verify_password.return_value = True
        mock_user_orm.is_verified = False
        mock_user_orm.is_active = True

        with pytest.raises(HTTPException) as exc_info:
            await user_service.authenticate_user("test@example.com", "pw")

        assert exc_info.value.status_code == 401
        assert "not verified" in exc_info.value.detail

    async def test_raises_401_when_account_deactivated(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_password_manager: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = mock_user_orm
        mock_password_manager.verify_password.return_value = True
        mock_user_orm.is_verified = True
        mock_user_orm.is_active = False

        with pytest.raises(HTTPException) as exc_info:
            await user_service.authenticate_user("test@example.com", "pw")

        assert exc_info.value.status_code == 401
        assert "deactivated" in exc_info.value.detail


# ---------------------------------------------------------------------------
# refresh_access_token
# ---------------------------------------------------------------------------


class TestRefreshAccessToken:
    async def test_returns_new_access_token_for_valid_refresh(
        self,
        user_service,
        mock_token_manager: MagicMock,
        mock_redis: AsyncMock,
        mock_user_orm: MagicMock,
    ) -> None:
        decoded = DecodedTokenSchema(
            email="test@example.com",
            id=mock_user_orm.id,
            role="user",
            purpose="refresh",
        )
        mock_token_manager.decode_token.return_value = decoded
        mock_redis.get.return_value = str(mock_user_orm.id)
        mock_token_manager.create_access_token.return_value = ("new_access_tok", 9999)

        access_token, expiry = await user_service.refresh_access_token("valid_refresh_tok")

        assert access_token == "new_access_tok"
        assert expiry == 9999

    async def test_raises_401_when_token_not_in_redis(
        self,
        user_service,
        mock_token_manager: MagicMock,
        mock_redis: AsyncMock,
        mock_user_orm: MagicMock,
    ) -> None:
        decoded = DecodedTokenSchema(
            email="test@example.com",
            id=mock_user_orm.id,
            role="user",
            purpose="refresh",
        )
        mock_token_manager.decode_token.return_value = decoded
        mock_redis.get.return_value = None  # token absent / expired

        with pytest.raises(HTTPException) as exc_info:
            await user_service.refresh_access_token("revoked_refresh_tok")

        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# logout_user
# ---------------------------------------------------------------------------


class TestLogoutUser:
    async def test_deletes_refresh_token_from_redis(
        self,
        user_service,
        mock_redis: AsyncMock,
    ) -> None:
        await user_service.logout_user("some_refresh_token")

        mock_redis.delete.assert_awaited_once_with("refresh:some_refresh_token")


# ---------------------------------------------------------------------------
# get_current_user_from_token
# ---------------------------------------------------------------------------


class TestGetCurrentUserFromToken:
    async def test_returns_current_user_info(
        self,
        user_service,
        mock_token_manager: MagicMock,
        mock_user_orm: MagicMock,
    ) -> None:
        decoded = DecodedTokenSchema(
            email="test@example.com",
            id=mock_user_orm.id,
            role="user",
            purpose="access",
        )
        mock_token_manager.decode_token.return_value = decoded

        result = await user_service.get_current_user_from_token("valid_access_token")

        assert result.email == "test@example.com"
        assert result.role == "user"
        mock_token_manager.decode_token.assert_called_once_with("valid_access_token")
