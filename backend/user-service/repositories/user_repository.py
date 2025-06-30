from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc
from pydantic import EmailStr

from models.user_models import User


class UserRepository:
    """Handles direct DB access for User entity. No business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # CREATE
    async def add_user(self, user: User) -> User:
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    # READ
    async def get_all_users(self) -> list[User]:
        result = await self.session.execute(select(User).order_by(asc(User.id)))
        return result.scalars().all()

    async def get_user_by_email(self, email: EmailStr) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalars().first()

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    # UPDATE
    async def update_user(self, user: User) -> User:
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    # DELETE
    async def delete_user(self, user: User) -> None:
        await self.session.delete(user)
        await self.session.commit()




