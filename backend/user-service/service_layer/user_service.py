from typing import Annotated
from uuid import UUID

from pydantic import EmailStr
from fastapi import Query

from models.user_models import User
from schemas.user_schemas import (
    UserSignUp,
    UserInfo,
    UserBasicUpdate,
    UsersFilterParams,
)
from shared.shared_instances import auth_manager
from exceptions.user_exceptions import (
    UserAlreadyExistsError,
    UserNotFoundError
)
from database_layer.user_repository import UserRepository


class UserService:
    """Service layer for user management operations, business logic and data validation."""
    def __init__(self, repository: UserRepository):
        self.repository = repository

    async def create_user(self, data: UserSignUp) -> UserInfo:
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
        return UserInfo.model_validate(user)

    async def get_all_users(self, filters: Annotated[UsersFilterParams, Query()]) -> list[UserInfo]:
        filters_dict = filters.model_dump()
        
        # Extracting pagination and sorting params
        offset = filters_dict.pop("offset", None)
        limit = filters_dict.pop("limit", None)
        sort_by = filters_dict.pop("sort_by", None)
        sort_order = filters_dict.pop("sort_order", "asc").lower()
        search_term = filters_dict.pop("search_term", None)
        
        # Range filters
        date_filters = {
            "date_created_from": filters_dict.pop("date_created_from", None),
            "date_created_to": filters_dict.pop("date_created_to", None),
            "date_updated_from": filters_dict.pop("date_updated_from", None),
            "date_updated_to": filters_dict.pop("date_updated_to", None)
        }
        
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
