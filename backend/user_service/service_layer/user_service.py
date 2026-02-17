from datetime import timedelta
from typing import Annotated
from uuid import UUID

from pydantic import EmailStr
from fastapi import Query
from fastapi.security import OAuth2PasswordRequestForm

from models.user_models import User
from shared.authentication import AuthenticationManager
from shared.schemas.user_schemas import (
    UserSignUp,
    UserInfo,
    UserBasicUpdate,
    UsersFilterParams,
)
from shared.shared_instances import auth_manager, settings
from exceptions.user_exceptions import (
    UserAlreadyExistsError,
    UserNotFoundError
)
from database_layer.user_repository import UserRepository
from events_publisher.user_events_publisher import notification_events_publisher


class UserService:
    """
    Service layer for user management operations, business logic and data validation.

    Responsibilities:
    - Business logic execution
    - Database operations via repository
    - Event publishing for state changes
    - Token generation for user actions
    """
    def __init__(self, repository: UserRepository):
        self.repository: UserRepository = repository
        self.auth_manager: AuthenticationManager = auth_manager

    async def create_user(self, data: UserSignUp) -> UserInfo:
        """
        Create a new user and publish registration event.

        Returns:
            tuple: (UserInfo, verification_token)

        Business Flow:
        1. Check if user exists
        2. Hash password
        3. Create user in database
        4. Generate verification token
        5. Publish user.registered event with token
        6. Return user info and token
        """
        existing_user = await self.repository.get_by_field("email", data.email)
        if existing_user:
            raise UserAlreadyExistsError(f"User with email: {data.email} already exists.")
        hashed_password = auth_manager.hash_password(data.password)
        new_user = User(
            name=data.name,
            email=data.email,
            hashed_password=hashed_password,
            is_verified=data.is_verified,
            role=data.role
        )
        user = await self.repository.create(new_user)
        verification_token, _ = self.auth_manager.create_access_token(
            email=user.email,
            user_id=user.id,
            role=user.role,
            expires_delta=timedelta(minutes=settings.TOKEN_TIME_DELTA_MINUTES),
            purpose="email_verification"
        )

        # This triggers the notification service to send verification email
        await notification_events_publisher.publish_user_registered(
            email=user.email,
            token=verification_token
        )
        return UserInfo.model_validate(user)

    async def login_user(self, form_data: OAuth2PasswordRequestForm) -> tuple:
        user = await self.auth_manager.get_authenticated_user(
            form_data=form_data, user_service=user_service
        )

        # creating access token
        access_token, expiry_timestamp = self.auth_manager.create_access_token(
            email=user.email,
            user_id=user.id,
            role=user.role,
            expires_delta=timedelta(minutes=settings.TOKEN_TIME_DELTA_MINUTES),
        )

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
        user = await self.repository.get_by_field(field_name="email", value=email)
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
        hashed_password = auth_manager.hash_password(new_password)
        updated_user = await self.repository.update_by_field(field_name="email", value=email, hashed_password=hashed_password)
        if not updated_user:
            raise UserNotFoundError(f"User with email {email} not found.")
        return UserInfo.model_validate(updated_user)

    async def update_user_basic_info(self, user_id: UUID, update_data: UserBasicUpdate) -> UserInfo:
        updated_user = await self.repository.update_by_id(item_id=user_id, **update_data.model_dump())
        if not updated_user:
            raise UserNotFoundError(f"User with id: {user_id} not found.")
        return UserInfo.model_validate(updated_user)

    async def update_user_verified_status(self, email: EmailStr, status: bool) -> UserInfo:
        updated_user = await self.repository.update_by_field(field_name="email", value=email, is_verified=status)
        if not updated_user:
            raise UserNotFoundError(f"User with email: {email} not found.")
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
