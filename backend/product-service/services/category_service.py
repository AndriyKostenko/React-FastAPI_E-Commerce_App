from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models.category_models import ProductCategory
from errors.category_errors import CategoryNotFoundError, CategoryCreationError


class CategoryCRUDService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_category(self, name: str, image_url: str) -> ProductCategory:
        db_category = await self.get_category_by_name(name)
        if db_category:
            raise CategoryCreationError(f'Category with name: "{name}" already exists.')
        new_category = ProductCategory(name=name, image_url=image_url)
        self.session.add(new_category)
        await self.session.commit()
        await self.session.refresh(new_category)
        return new_category
   

    async def get_all_categories(self):
        result = await self.session.execute(select(ProductCategory))
        categories = result.scalars().all()
        return categories

    async def get_category_by_id(self, category_id: UUID):
        result = await self.session.execute(select(ProductCategory).where(ProductCategory.id == category_id))
        category = result.scalars().first()
        if not category:
            raise CategoryNotFoundError(f'Category with id: "{category_id}" not found.')
        return category

    async def get_category_by_name(self, name: str):
        result = await self.session.execute(select(ProductCategory).where(func.lower(ProductCategory.name) == name.lower()))
        category = result.scalars().first()
        if not category:
            raise CategoryNotFoundError(f'Category with name: "{name}" not found.')
        return category

    async def delete_category(self, category_id: UUID):
        category = await self.get_category_by_id(category_id)
        await self.session.delete(category)
        await self.session.commit()


    async def update_category(self, category_id: UUID, name: str, image_url: str):
        category = await self.get_category_by_id(category_id)
        if name:
            category.name = name
        if image_url:
            category.image_url = image_url
        await self.session.commit()
        await self.session.refresh(category)
        return category
        