from datetime import timedelta
from typing import Annotated
from uuid import UUID

from pydantic import EmailStr
from fastapi import Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.exceptions import HTTPException
from sqlalchemy.ext.asyncio.session import AsyncSession

from models.user_models import User
from shared.schemas.user_schemas import CurrentUserInfo
from shared.schemas.user_schemas import (
    UserSignUp,
    UserInfo,
    UserBasicUpdate,
    UsersFilterParams,
)
from shared.shared_instances import settings
from exceptions.user_exceptions import (
    UserAlreadyExistsError,
    UserNotFoundError,
    UserUpdateError
)
from database_layer.user_repository import UserRepository
from shared.password_manager import PasswordManager
from shared.token_manager import TokenManager





class UserService:
    """
    Service layer for user management operations, business logic and data validation.

    Responsibilities:
    - Business logic execution
    - Database operations via repository
    - Event publishing for state changes
    """
    def __init__(self,
                repository: UserRepository,
                password_manager: PasswordManager,
                token_manager: TokenManager):
        self.repository: UserRepository = repository
        self.password_manager: PasswordManager = password_manager
        self.token_manager: TokenManager = token_manager

    async def create_user(self, data: UserSignUp) -> tuple[UserInfo , str]:
        """
        Create a new user and publish registration event.

        Returns:
            tuple: (UserInfo, verification_token)
        """
        existing_user = await self.repository.get_by_field("email", data.email)
        if existing_user:
            raise UserAlreadyExistsError(f"User with email: {data.email} already exists.")
        hashed_password = self.password_manager.hash_password(data.password)
        new_user = User(
            name=data.name,
            email=data.email,
            hashed_password=hashed_password,
            is_verified=False,
            role="user",
            is_active=True,
        )
        user = await self.repository.create(new_user)
        verification_token, _ = self.token_manager.create_access_token(
            email=user.email,
            user_id=user.id,
            role=user.role,
            expires_delta=timedelta(minutes=settings.VERIFICATION_TOKEN_EXPIRY_MINUTES),
            purpose="email_verification"
        )

        return UserInfo.model_validate(user), verification_token

    async def verify_password(self, email: EmailStr, password: str) -> bool:
        user = await self.repository.get_by_field("email", email)
        if not user:
            raise UserNotFoundError(f"User with email: {email} is not found")
        return self.password_manager.verify_password(password, user.hashed_password)

    async def login_user(self, form_data: OAuth2PasswordRequestForm) -> tuple[CurrentUserInfo, str, int]:
        current_user, access_token, expiry_timestamp = await self.authenticate_user(email=form_data.username, password=form_data.password)
        await notification_events_publisher.publish_user_logged_in(email=current_user.email)
        return current_user, access_token, expiry_timestamp

    async def get_all_users(self, filters: Annotated[UsersFilterParams, Query()]) -> list[UserInfo]:
        filters_dict = filters.model_dump()

        # Extracting pagination and sorting params
        offset = filters_dict.pop("offset", None)
        limit = filters_dict.pop("limit", None)
        sort_by = filters_dict.pop("sort_by", None)
        sort_order = filters_dict.pop("sort_order", "asc").lower()
        search_term = filters_dict.pop("search_term", None)

        # Range filters
        date_filters = {"date_created_from": filters_dict.pop("date_created_from", None),
                        "date_created_to": filters_dict.pop("date_created_to", None),
                        "date_updated_from": filters_dict.pop("date_updated_from", None),
                        "date_updated_to": filters_dict.pop("date_updated_to", None)}

        # Remaining filters
        cleaned_filters = {key: value for key, value in filters_dict.items() if value is not None}

        # General query params
        users = await self.repository.get_all(filters=cleaned_filters,
                                              sort_by=sort_by,
                                              sort_order=sort_order,
                                              offset=offset,
                                              limit=limit,
                                              search_term=search_term,
                                              date_filters=date_filters,
                                              search_fields=User.get_search_fields())
        if not users:
            raise UserNotFoundError("No users found with the given criteria.")
        return [UserInfo.model_validate(user) for user in users]

    async def get_user_by_email(self, email: EmailStr) -> UserInfo:
        user: User | None = await self.repository.get_by_field(field_name="email", value=email)
        if not user:
            raise UserNotFoundError(f"User with email {email} not found.")
        return UserInfo.model_validate(user)

    async def get_user_by_id(self, user_id: UUID) -> UserInfo:
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id {user_id} not found.")
        return UserInfo.model_validate(user)

    async def get_user_hashed_password(self, email: EmailStr) -> str:
        user = await self.repository.get_by_field(field_name="email", value=email)
        if not user:
            raise UserNotFoundError(f"User with email {email} not found.")
        return user.hashed_password

    async def update_user_password(self, email: EmailStr, new_password: str) -> UserInfo:
        hashed_password = self.password_manager.hash_password(new_password)
        updated_user = await self.repository.update_by_field(field_name="email", value=email, hashed_password=hashed_password)
        if not updated_user:
            raise UserNotFoundError(f"User with email {email} not found.")
        return UserInfo.model_validate(updated_user)

    async def update_user_basic_info(self, user_id: UUID, update_data: UserBasicUpdate) -> UserInfo:
        updated_user = await self.repository.update_by_id(item_id=user_id, **update_data.model_dump())
        if not updated_user:
            raise UserNotFoundError(f"User with id: {user_id} not found.")
        return UserInfo.model_validate(updated_user)

    async def verify_email(self, token: str) -> UserInfo:
        token_data = self.token_manager.decode_token(
            token=token,
            required_purpose="email_verification")
        updated_user = await self.repository.update_by_field(
            field_name="email",
            value=token_data["email"],
            is_verified=True)
        if not updated_user:
            raise UserNotFoundError("User not found for verification")
        await notification_events_publisher.publish_email_verified(email=updated_user.email)
        return UserInfo.model_validate(updated_user)

    async def delete_user_by_id(self, user_id: UUID) -> None:
        success = await self.repository.delete_by_id(user_id)
        if not success:
            raise UserNotFoundError(f"User with id: {user_id} not found.")

    async def get_verified_users(self) -> list[UserInfo]:
        users =  await self.repository.get_verified_users()
        return [UserInfo.model_validate(user) for user in users]

    async def get_by_role(self, role: str) -> list[UserInfo]:
        users = await self.repository.get_users_by_role(role=role)
        return [UserInfo.model_validate(user) for user in users]

    async def request_password_reset(self, email: EmailStr) -> None:
        user = await self.repository.get_by_field("email", email)
        if not user:
            raise UserNotFoundError("User not found")
        reset_token, _ = self.token_manager.create_access_token(
            email=user.email,
            user_id=user.id,
            role=user.role,
            expires_delta=timedelta(minutes=settings.RESET_TOKEN_EXPIRY_MINUTES),
            purpose="password_reset"
        )
        await notification_events_publisher.publish_password_reset_request(
            email=user.email,
            reset_token=reset_token
        )

    async def reset_password_with_token(self, token: str, new_password: str) -> UserInfo:
        token_data = self.token_manager.decode_token(
            token=token,
            required_purpose="password_reset"
        )
        hashed_password = self.password_manager.hash_password(new_password)
        updated_user = await self.repository.update_by_field(
            field_name="email",
            value=token_data["email"],
            hashed_password=hashed_password
        )
        if not updated_user:
            raise UserUpdateError("Password reset failed")
        await notification_events_publisher.publish_password_reset_success(
            email=updated_user.email
        )
        return UserInfo.model_validate(updated_user)

    async def authenticate_user(self,
                                email: EmailStr,
                                password: str) -> tuple[CurrentUserInfo, str, int]:
        """
        Authenticate user with email and password.

        Returns:
            tuple: (CurrentUserInfo, access_token, expiry_timestamp)
        """
        is_valid = await self.verify_password(email, password)
        if not is_valid:
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        user = await self.get_user_by_email(email)
        if not user.is_verified:
            raise HTTPException(status_code=401, detail="User is not verified")
        if not user.is_active:                                          # ← missing
            raise HTTPException(status_code=401, detail="Account is deactivated")

        access_token, expiry_timestamp = self.token_manager.create_access_token(
            email=email,
            user_id=user.id,
            role=user.role,
            expires_delta=timedelta(minutes=settings.TOKEN_TIME_DELTA_MINUTES),
            purpose="access"
        )
        current_user = CurrentUserInfo(
            email=user.email,
            id=user.id,
            role=user.role
        )
        return current_user, access_token, expiry_timestamp

    async def get_current_user_from_token(self, token: str) -> CurrentUserInfo:
        user_info = self.token_manager.decode_token(token)
        return CurrentUserInfo(
            email=user_info["email"],
            id=user_info["id"],
            role=user_info["role"]
        )
