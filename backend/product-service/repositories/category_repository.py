from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc

from models.category_models import ProductCategory


class CategoryRepository:
    """Handles direct DB access for Category entity. No business logic."""
    
    def __init__(self, session: AsyncSession):
        self.session = session

    # CREATE
    async def add_category(self, category: ProductCategory) -> ProductCategory:
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        return category

    # READ
    async def get_all_categories(self) -> list[ProductCategory]:
        result = await self.session.execute(select(ProductCategory).order_by(asc(ProductCategory.id)))
        return result.scalars().all()
    
    async def get_category_by_id(self, category_id: UUID) -> Optional[ProductCategory]:
        result = await self.session.execute(select(ProductCategory).where(ProductCategory.id == category_id))
        return result.scalars().first()
    
    async def get_category_by_name(self, name: str) -> Optional[ProductCategory]:
        result = await self.session.execute(select(ProductCategory).where(ProductCategory.name == name))
        return result.scalars().first()
    
    # UPDATE
    async def update_category(self, category: ProductCategory) -> ProductCategory:
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        return category
    
    # DELETE
    async def delete_category(self, category: ProductCategory) -> None:
        await self.session.delete(category)
        await self.session.commit()