"""
Unit tests for UserService.

All external dependencies (repository, password manager, token manager,
Redis) are mocked so every test runs without a live database or cache.
Tests are grouped by service method using classes for readability.
"""
from datetime import datetime
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from exceptions.user_exceptions import (
    UserAlreadyExistsError,
    UserNotFoundError,
    UserUpdateError,
)
from schemas.user_schemas import (
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
        mock_redis: AsyncMock,
        mock_outbox_event_service: MagicMock,
    ) -> None:
        mock_repository.create.return_value = mock_user_orm

        data = UserSignUp(name="Test User", email="test@example.com", password="password123")
        with patch("service_layer.user_service.secrets.token_urlsafe", return_value="verify_tok"):
            user_info, token = await user_service.create_user(data)

        assert user_info.email == "test@example.com"
        assert token == "verify_tok"
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        mock_redis.setex.assert_awaited_once_with(
            f"verify_email:{token_hash}",
            user_service.settings.VERIFICATION_TOKEN_EXPIRY_MINUTES * 60,
            str(mock_user_orm.id),
        )
        mock_repository.get_by_field.assert_not_awaited()
        mock_repository.create.assert_awaited_once()
        mock_outbox_event_service.add_outbox_event.assert_awaited_once()

    async def test_raises_when_email_already_registered(
        self,
        user_service,
        mock_repository: MagicMock,
    ) -> None:
        mock_repository.create.side_effect = IntegrityError(
            "duplicate email", params={}, orig=Exception("unique constraint")
        )

        data = UserSignUp(name="Test User", email="test@example.com", password="password123")
        with pytest.raises(UserAlreadyExistsError):
            await user_service.create_user(data)

        mock_repository.get_by_field.assert_not_awaited()

    async def test_hashes_plain_password_before_saving(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_password_manager: MagicMock,
        mock_outbox_event_service: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = None
        mock_repository.create.return_value = mock_user_orm

        data = UserSignUp(name="Test User", email="test@example.com", password="plain_pw")
        await user_service.create_user(data)

        mock_password_manager.hash_password.assert_called_once_with("plain_pw")
        mock_outbox_event_service.add_outbox_event.assert_awaited_once()


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

    async def test_returns_empty_list_when_query_returns_no_users(
        self,
        user_service,
        mock_repository: MagicMock,
    ) -> None:
        mock_repository.get_all.return_value = []

        assert await user_service.get_all_users(UsersFilterParams()) == []


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
            item_id=mock_user_orm.id, data={"name": "New Name"}
        )

    async def test_rejects_an_empty_update(
        self,
        user_service,
        mock_repository: MagicMock,
    ) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await user_service.update_user_basic_info(uuid4(), UserBasicUpdate())

        assert exc_info.value.status_code == 400
        mock_repository.update_by_id.assert_not_awaited()

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
        mock_redis: AsyncMock,
        mock_outbox_event_service: MagicMock,
    ) -> None:
        mock_redis.getdel.return_value = str(mock_user_orm.id)
        mock_repository.get_by_id.return_value = mock_user_orm
        mock_repository.update_by_field.return_value = mock_user_orm

        result = await user_service.verify_email("verification_token")

        assert result.email == "test@example.com"
        token_hash = hashlib.sha256(b"verification_token").hexdigest()
        mock_redis.getdel.assert_awaited_once_with(f"verify_email:{token_hash}")
        mock_repository.get_by_id.assert_awaited_once_with(mock_user_orm.id)
        mock_repository.update_by_field.assert_awaited_once_with(
            field_name="email", value=mock_user_orm.email, is_verified=True
        )
        mock_outbox_event_service.add_outbox_event.assert_awaited_once()

    async def test_raises_when_user_not_found_after_token_lookup(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_redis: AsyncMock,
    ) -> None:
        mock_redis.getdel.return_value = str(mock_user_orm.id)
        mock_repository.get_by_id.return_value = None

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
        mock_user_orm: MagicMock,
        mock_outbox_event_service: MagicMock,
    ) -> None:
        mock_repository.get_by_id.return_value = mock_user_orm
        mock_repository.update_by_id.return_value = mock_user_orm
        user_id = mock_user_orm.id

        await user_service.delete_user_by_id(user_id)  # must not raise

        mock_repository.get_by_id.assert_awaited_once_with(user_id)
        mock_repository.delete_by_id.assert_not_awaited()
        update_call = mock_repository.update_by_id.await_args
        assert update_call.kwargs["item_id"] == user_id
        changes = update_call.kwargs["data"]
        assert changes["name"] == "Deleted user"
        assert changes["email"] == f"deleted+{user_id}@invalid.local"
        assert changes["hashed_password"] is None
        assert changes["is_active"] is False
        assert changes["token_version"] == 2
        assert isinstance(changes["deleted_at"], datetime)
        mock_outbox_event_service.add_outbox_event.assert_awaited_once()

    async def test_raises_when_user_not_found(
        self,
        user_service,
        mock_repository: MagicMock,
    ) -> None:
        mock_repository.get_by_id.return_value = None

        with pytest.raises(UserNotFoundError):
            await user_service.delete_user_by_id(uuid4())

        mock_repository.update_by_id.assert_not_awaited()


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
        mock_redis: AsyncMock,
        mock_outbox_event_service: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = mock_user_orm

        with patch("service_layer.user_service.secrets.token_urlsafe", return_value="reset_tok"):
            user, token = await user_service.request_password_reset("test@example.com")

        assert user.email == "test@example.com"
        assert token == "reset_tok"
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        mock_redis.setex.assert_awaited_once_with(
            f"pwd_reset:{token_hash}",
            user_service.settings.RESET_TOKEN_EXPIRY_MINUTES * 60,
            str(mock_user_orm.id),
        )
        mock_outbox_event_service.add_outbox_event.assert_awaited_once()

    async def test_returns_generic_result_when_user_not_found(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_outbox_event_service: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = None

        assert await user_service.request_password_reset("ghost@example.com") == (None, "")
        mock_outbox_event_service.add_outbox_event.assert_not_awaited()


# ---------------------------------------------------------------------------
# reset_password_with_token
# ---------------------------------------------------------------------------


class TestResetPasswordWithToken:
    async def test_resets_password_successfully(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_redis: AsyncMock,
        mock_password_manager: MagicMock,
        mock_outbox_event_service: MagicMock,
    ) -> None:
        mock_redis.getdel.return_value = str(mock_user_orm.id)
        mock_repository.get_by_id.return_value = mock_user_orm
        mock_repository.update_by_id.return_value = mock_user_orm
        mock_password_manager.hash_password.return_value = "new_hashed_pw"

        result = await user_service.reset_password_with_token("reset_token", "new_pw123")

        assert result.email == "test@example.com"
        token_hash = hashlib.sha256(b"reset_token").hexdigest()
        mock_redis.getdel.assert_awaited_once_with(f"pwd_reset:{token_hash}")
        mock_password_manager.hash_password.assert_called_once_with("new_pw123")
        mock_repository.update_by_id.assert_awaited_once_with(
            item_id=mock_user_orm.id,
            data={"hashed_password": "new_hashed_pw", "token_version": 2},
        )
        mock_outbox_event_service.add_outbox_event.assert_awaited_once()

    async def test_raises_when_db_update_fails(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_redis: AsyncMock,
    ) -> None:
        mock_redis.getdel.return_value = str(mock_user_orm.id)
        mock_repository.get_by_id.return_value = mock_user_orm
        mock_repository.update_by_id.return_value = None

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
        pipeline = mock_redis.pipeline.return_value
        pipeline.setex.assert_called_once()
        pipeline.sadd.assert_called_once()
        pipeline.expire.assert_called_once()
        pipeline.execute.assert_awaited_once()

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
# login_user
# ---------------------------------------------------------------------------


class TestLoginUser:
    async def test_authenticates_and_creates_login_outbox_event(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_user_orm: MagicMock,
        mock_password_manager: MagicMock,
        mock_token_manager: MagicMock,
        mock_redis: AsyncMock,
        mock_outbox_event_service: MagicMock,
    ) -> None:
        mock_repository.get_by_field.return_value = mock_user_orm
        mock_password_manager.verify_password.return_value = True
        mock_user_orm.is_verified = True
        mock_user_orm.is_active = True
        mock_token_manager.create_access_token.return_value = ("access_tok", 9999)
        mock_token_manager.create_refresh_token.return_value = ("refresh_tok", 9999)

        form_data = MagicMock()
        form_data.username = "test@example.com"
        form_data.password = "correct_pw"

        user, access_token, _, refresh_token, _ = await user_service.login_user(form_data)

        assert user.email == "test@example.com"
        assert access_token == "access_tok"
        assert refresh_token == "refresh_tok"
        mock_redis.pipeline.return_value.execute.assert_awaited_once()
        mock_outbox_event_service.add_outbox_event.assert_awaited_once()


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
            token_version=1,
        )
        mock_token_manager.decode_token.return_value = decoded
        mock_redis.getdel.return_value = str(mock_user_orm.id)
        mock_repository = user_service.repository
        mock_repository.get_by_id.return_value = mock_user_orm
        mock_token_manager.create_access_token.return_value = ("new_access_tok", 9999)
        mock_token_manager.create_refresh_token.return_value = ("rotated_refresh_tok", 19999)

        access_token, expiry, refresh_token, refresh_expiry = await user_service.refresh_access_token(
            "valid_refresh_tok"
        )

        assert access_token == "new_access_tok"
        assert expiry == 9999
        assert refresh_token == "rotated_refresh_tok"
        assert refresh_expiry == 19999
        mock_redis.srem.assert_awaited_once()
        mock_redis.pipeline.return_value.execute.assert_awaited_once()

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
            token_version=1,
        )
        mock_token_manager.decode_token.return_value = decoded
        mock_redis.getdel.return_value = None  # token absent / expired

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

        token_hash = hashlib.sha256(b"some_refresh_token").hexdigest()
        mock_redis.delete.assert_awaited_once_with(f"refresh:{token_hash}")


# ---------------------------------------------------------------------------
# get_current_user_from_token
# ---------------------------------------------------------------------------


class TestGetCurrentUserFromToken:
    async def test_returns_current_user_info(
        self,
        user_service,
        mock_repository: MagicMock,
        mock_token_manager: MagicMock,
        mock_user_orm: MagicMock,
    ) -> None:
        decoded = DecodedTokenSchema(
            email="test@example.com",
            id=mock_user_orm.id,
            role="user",
            purpose="access",
            token_version=1,
        )
        mock_token_manager.decode_token.return_value = decoded
        mock_repository.get_by_id.return_value = mock_user_orm

        result = await user_service.get_current_user_from_token("valid_access_token")

        assert result.email == "test@example.com"
        assert result.role == "user"
        mock_token_manager.decode_token.assert_called_once_with(
            "valid_access_token", required_purpose="access"
        )
