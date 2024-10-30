from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.category_models import Category
from src.schemas.category_schema import CreateCategory



class CategoryCRUDService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_category(self, name: str, image_url: str):
        db_category = await self.session.execute(select(Category).where(Category.name == name))
        db_category = db_category.scalars().first()
        if db_category:
            return db_category

        new_category = Category(name=name, image_url=image_url)
        self.session.add(new_category)
        await self.session.commit()
        return new_category

    async def get_all_categories(self):
        result = await self.session.execute(select(Category))
        categories = result.scalars().all()
        return categories

    async def get_category_by_id(self, category_id: int):
        result = await self.session.execute(select(Category).where(Category.id == category_id))
        category = result.scalars().first()
        return category

    async def delete_category(self, category_id: int):
        result = await self.session.execute(select(Category).where(Category.id == category_id))
        category = result.scalars().first()
        if category:
            await self.session.delete(category)
            await self.session.commit()
        return category

    async def update_category(self, id: str, name: str, image_url: str):
        result = await self.session.execute(select(Category).where(Category.id == id))
        category = result.scalars().first()
        if category:
            if name is not None:
                category.name = name
            if image_url is not None:
                category.image_url = image_url
            await self.session.commit()
        return category