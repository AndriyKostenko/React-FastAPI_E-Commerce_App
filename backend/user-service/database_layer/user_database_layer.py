from shared.database_layer import BaseRepository
from sqlalchemy.ext.asyncio import AsyncSession
from models.user_models import User 
from pydantic import EmailStr
from typing import Optional, Dict
 

class UserRepository(BaseRepository):
    """
    User-specific database service layer with additional methods.
    Inherits all CRUD operations from BaseRepository.
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_by_email(self, email: EmailStr) -> Optional[User]:
        """Get user by email - specific to User model"""
        return await self.get_by_field("email", email)

    async def get_verified_users(self) -> list[User]:
        """Get all verified users"""
        return await self.filter_by(is_verified=True)

    async def get_by_role(self, role: str) -> list[User]:
        """Get users by role"""
        return await self.filter_by(role=role)
    
    