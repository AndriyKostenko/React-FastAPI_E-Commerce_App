from uuid import UUID

from pydantic import EmailStr

from database_layer.user_database_layer import UserRepository
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


class UserService:
    """Service layer for user management operations, business logic and data validation."""
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def create_user(self, data: UserSignUp) -> UserInfo:
        existing_user = await self.get_user_by_email(data.email)
        if existing_user:
            raise UserAlreadyExistsError(f"User with email {data.email} already exists.")

        hashed_password = auth_manager.hash_password(data.password)
        new_user = User(
            name=data.name,
            email=data.email,
            hashed_password=hashed_password,
            is_verified=data.is_verified,
            role=data.role
        )

        user = await self.repo.create(new_user)
        return UserInfo.model_validate(user)

    async def get_all_users(self) -> list[UserInfo]:
        users = await self.repo.get_all()
        return [UserInfo.model_validate(user) for user in users]

    async def get_user_by_email(self, email: EmailStr) -> UserInfo:
        user = await self.repo.get_by_email(email)
        if not user:
            raise UserNotFoundError(f"User with email {email} not found.")
        return UserInfo.model_validate(user)

    async def get_user_by_id(self, user_id: UUID) -> UserInfo:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id {user_id} not found.")
        return UserInfo.model_validate(user)
    
    async def get_user_hashed_password(self, email: EmailStr) -> str:
        user = await self.repo.get_by_email(email)
        if not user:
            raise UserNotFoundError(f"User with email {email} not found.")
        return user.hashed_password


    async def update_user_basic_info(self, user_id: UUID, update_data: UserBasicUpdate) -> UserInfo:
        updated_user = await self.repo.update_by_id(user_id, update_data)
        if not updated_user:
            raise UserNotFoundError(f"User with id {user_id} not found.")
        return UserInfo.model_validate(updated_user)


    async def delete_user_by_id(self, user_id: UUID) -> None:
        await self.repo.delete_by_id(user_id)
      
