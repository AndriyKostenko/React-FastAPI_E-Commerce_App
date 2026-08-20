from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.category_models import ProductCategory
from shared.database_layer.database_layer import BaseRepository


class CategoryRepository(BaseRepository[ProductCategory]):
    """
    This class extends BaseRepository to provide specific methods
    for managing categories in the database.
    """
    def __init__(self, session: AsyncSession):
        super().__init__(session, ProductCategory)

    async def get_or_create_id_by_name(self, name: str) -> UUID:
        statement = (
            insert(ProductCategory)
            .values(name=name)
            .on_conflict_do_nothing(index_elements=["name"])
            .returning(ProductCategory.id)
        )
        created_id = (await self.session.execute(statement)).scalar_one_or_none()
        if created_id:
            return created_id
        existing_id = (
            await self.session.execute(
                select(ProductCategory.id).where(ProductCategory.name == name)
            )
        ).scalar_one()
        return existing_id
