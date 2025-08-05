from dataclasses import field
from uuid import UUID

from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from models.user_models import User
from schemas.user_schemas import (
    UserSignUp,
    UserInfo,
    UserBasicUpdate,
)
from authentication import auth_manager
from errors.errors import (
    UserAlreadyExistsError,
    UserNotFoundError
)
from shared.database_layer import BaseRepository
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

    async def get_all_users(self) -> list[UserInfo]:
        users = await self.repository.get_all()
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
        updated_user = await self.repository.update_by_id(id=user_id, update_data=update_data)
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
        """Get all verified users"""
        users =  await self.repository.get_verified_users()
        return [UserInfo.model_validate(user) for user in users]

    async def get_by_role(self, role: str) -> list[UserInfo]:
        """Get users by role"""
        users = await self.repository.get_users_by_role(role=role)
        return [UserInfo.model_validate(user) for user in users]
