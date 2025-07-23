from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc

from models.category_models import ProductCategory
from shared.database_layer import BaseRepository


class CategoryRepository(BaseRepository):
    """
    Category-specific repository with additional methods.
    Inherits from BaseRepository to manage database CRUD operations for Category entities
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, ProductCategory)
        
    async def get_category_by_name(self, name: str) -> Optional[ProductCategory]:
        return await self.get_by_field("name", name)
    
    async def get_category_by_id(self, category_id: UUID) -> Optional[ProductCategory]:
        return await self.get_by_id(category_id)
    
    async def get_all_categories(self) -> list[ProductCategory]:
        return await self.get_all()