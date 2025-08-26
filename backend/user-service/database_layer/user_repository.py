from sqlalchemy.ext.asyncio import AsyncSession

from models.user_models import User
from shared.database_layer import BaseRepository


class UserRepository(BaseRepository[User]):
    """
    This class extends BaseRepository to provide specific methods
    for managing users in the database.
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_users_by_role(self, role: str) -> list[User]:
        """Get all users with specific role"""
        return await self.filter_by(role=role)

    async def get_verified_users(self) -> list[User]:
        """Get all verified users"""
        return await self.filter_by(is_verified=True)

    async def get_unverified_users(self) -> list[User]:
        """Get all unverified users"""
        return await self.filter_by(is_verified=False)