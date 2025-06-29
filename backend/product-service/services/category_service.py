from datetime import datetime, timezone
from re import A
from uuid import UUID
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.category_models import ProductCategory
from errors.category_errors import CategoryNotFoundError, CategoryCreationError
from schemas.category_schema import CategorySchema

class CategoryCRUDService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_category(self, name: str, image_url: str) -> CategorySchema:
        db_category = await self._check_category_exists_by_name(name.lower())
        if db_category:
            raise CategoryCreationError(f'Category with name: "{name}" already exists.')
        new_category = ProductCategory(name=name.lower(), 
                                       image_url=image_url,
                                       date_created=datetime.now(timezone.utc))
        self.session.add(new_category)
        await self.session.commit()
        await self.session.refresh(new_category)
        return CategorySchema.model_validate(new_category)
   
    async def get_all_categories(self) -> List[CategorySchema]:
        """Fetch all product categories from the database."""
        result = await self.session.execute(select(ProductCategory))
        categories = result.scalars().all()
        return [CategorySchema.model_validate(category) for category in categories]
    
    async def _check_category_exists_by_name(self, name: str) -> bool:
        """Internal method to check if category exists without raising exceptions"""
        query = await self.session.execute(select(ProductCategory).where(ProductCategory.name == name.lower()))
        category = query.scalars().first()
        return category is not None
    
    async def _check_category_exists_by_id(self, category_id: UUID) -> bool:
        """Internal method to check if category exists without raising exceptions"""
        query = await self.session.execute(select(ProductCategory).where(ProductCategory.id == category_id))
        category = query.scalars().first()
        return category is not None

    async def get_category_by_id(self, category_id: UUID) -> CategorySchema:
        """Fetch a category by its ID."""
        result = await self.session.execute(select(ProductCategory).where(ProductCategory.id == category_id))
        category = result.scalars().first()
        if not category:
            raise CategoryNotFoundError(f'Category with id: "{category_id}" not found.')
        return CategorySchema.model_validate(category)
    
    async def get_category_by_name(self, name: str) -> CategorySchema:
        result = await self.session.execute(select(ProductCategory).where(ProductCategory.name == name.lower()))
        category = result.scalars().first()
        if not category:
            raise CategoryNotFoundError(f'Category with name: "{name}" not found.')
        return CategorySchema.model_validate(category)

    async def delete_category(self, category_id: UUID):
        """Delete a category by its ID."""
        category = await self.get_category_by_id(category_id)
        await self.session.delete(category)
        await self.session.commit()

    async def update_category(self, category_id: UUID, name: str | None, image_url: str | None) -> CategorySchema:
        """Update a category's name and/or image URL."""
        category = await self.get_category_by_id(category_id)
        if name:
            category.name = name
        if image_url:
            category.image_url = image_url
        await self.session.commit()
        await self.session.refresh(category)
        return CategorySchema.model_validate(category)
        