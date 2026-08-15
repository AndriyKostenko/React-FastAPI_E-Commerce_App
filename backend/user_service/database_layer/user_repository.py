from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user_models import User
from shared.database_layer.database_layer import BaseRepository
from shared.database_layer.repository_mixins import AdvancedQueryMixin


class UserRepository(AdvancedQueryMixin[User], BaseRepository[User]):
    """
    Repository for user-specific database operations.
    """

    # String fields that must use equality rather than ILIKE in get_all().
    EQUAL_ONLY_FIELDS: list[str] = ["id", "uuid", "email", "phone_number"]

    def __init__(self, session: AsyncSession):
        super().__init__(session, User)
        self.search_fields: list[str] = User.get_search_fields()

    async def get_by_id(self, item_id, load_relations=None):
        result = await self.session.execute(
            select(User).where(User.id == item_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_field(self, field_name, value):
        if not hasattr(User, field_name):
            return await super().get_by_field(field_name, value)
        result = await self.session.execute(
            select(User).where(getattr(User, field_name) == value, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def search(self,
                    filters: dict[str, Any],
                    search_term: str | None,
                    limit: int,
                    offset: int):
        """Search users based on filters and search term"""
        return await self.get_all(
            filters=filters,
            search_fields=self.search_fields,
            search_term=search_term,
            limit=limit,
            offset=offset
        )

    async def get_users_by_role(self, role: str) -> list[User]:
        """Get all users with specific role"""
        return await self.filter_by(role=role)

    async def get_verified_users(self) -> list[User]:
        """Get all verified users"""
        return await self.filter_by(is_verified=True)

    async def get_unverified_users(self) -> list[User]:
        """Get all unverified users"""
        return await self.filter_by(is_verified=False)
