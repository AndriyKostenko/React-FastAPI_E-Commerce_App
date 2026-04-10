from sqlalchemy.ext.asyncio import AsyncSession

from models.user_models import User
from shared.database_layer import BaseRepository # type: ignore


class UserRepository(BaseRepository[User]):
    """
    This class extends BaseRepository to provide specific methods
    for managing users in the database.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, User)
        self.search_fields = User.get_search_fields()


    # TODO: make this repository more specific to user and make BaseRepository simplier for basic CRUD operations
    async def search(self,
                    filters: dict,
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
