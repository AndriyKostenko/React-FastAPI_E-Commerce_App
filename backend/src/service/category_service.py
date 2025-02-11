from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from src.models.category_models import ProductCategory
from src.schemas.category_schema import CreateCategory



class CategoryCRUDService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_category(self, name: str, image_url: str):
        db_category = await self.get_category_by_name(name)

        if db_category:
            return db_category

        new_category = ProductCategory(name=name, image_url=image_url)
        self.session.add(new_category)

        try:
            await self.session.commit()
            await self.session.refresh(new_category)
            return new_category
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise ValueError(f"Database error while creating category: {str(e)}")

    async def get_all_categories(self):
        result = await self.session.execute(select(ProductCategory))
        categories = result.scalars().all()
        return categories

    async def get_category_by_id(self, category_id: str):
        result = await self.session.execute(select(ProductCategory).where(ProductCategory.id == category_id))
        category = result.scalars().first()
        return category

    async def get_category_by_name(self, name: str):
        result = await self.session.execute(select(ProductCategory).where(func.lower(ProductCategory.name) == name.lower()))
        category = result.scalars().first()
        return category

    async def delete_category(self, category_id: str):
        category = await self.get_category_by_id(category_id)
        if not category:
            return None
        try:
            await self.session.delete(category)
            await self.session.commit()
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise ValueError(f"Database error while deleting category: {str(e)}")

    async def update_category(self, category_id: str, name: str, image_url: str):
        category = await self.get_category_by_id(category_id)
        if not category:
            return None
        if name:
            category.name = name
        if image_url:
            category.image_url = image_url
        try:
            await self.session.commit()
            await self.session.refresh(category)
            return category
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise ValueError(f"Database error while updating category: {str(e)}")