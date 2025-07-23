from uuid import UUID

from models.category_models import ProductCategory
from errors.category_errors import CategoryNotFoundError, CategoryCreationError
from schemas.category_schema import CategorySchema, CreateCategory, UpdateCategory
from database_layer.category_repository import CategoryRepository


class CategoryService:
    """Service layer for category management operations, business logic and data validation."""
    def __init__(self, repo: CategoryRepository):
        self.repo = repo

    async def create_category(self, category_data: CreateCategory ) -> CategorySchema:
        db_category = await self.repo.get_category_by_name(name=category_data.name.lower())
        if db_category:
            raise CategoryCreationError(f'Category with name: "{category_data.name}" already exists.')
        new_category = ProductCategory(name=category_data.name.lower(), 
                                       image_url=category_data.image_url)
        new_db_category = await self.repo.add_category(new_category)
        return CategorySchema.model_validate(new_db_category)
   
    async def get_all_categories(self) -> list[CategorySchema]:
        categories = await self.repo.get_all_categories()
        if not categories or len(categories) == 0:
            raise CategoryNotFoundError("No categories found.")
        return [CategorySchema.model_validate(category) for category in categories]

    async def get_category_by_id(self, category_id: UUID) -> CategorySchema:
        category = await self.repo.get_category_by_id(category_id)
        if not category:
            raise CategoryNotFoundError(f'Category with id: "{category_id}" not found.')
        return CategorySchema.model_validate(category)
    
    async def get_category_by_name(self, name: str) -> CategorySchema:
        category = await self.repo.get_category_by_name(name=name.lower())
        if not category:
            raise CategoryNotFoundError(f'Category with name: "{name}" not found.')
        return CategorySchema.model_validate(category)

    async def update_category(self, category_id: UUID, data: UpdateCategory) -> CategorySchema:
        category = await self.repo.get_category_by_id(category_id)
        if not category:
            raise CategoryNotFoundError(f'Category with id: "{category_id}" not found.')
        
        for key, value in data.model_dump().items():
            if value is not None:
                setattr(category, key, value)
        category = await self.repo.update_category(category)
        return CategorySchema.model_validate(category)
    
    async def delete_category(self, category_id: UUID) -> None:
        category = await self.repo.get_category_by_id(category_id)
        if not category:
            raise CategoryNotFoundError(f'Category with id: "{category_id}" not found.')
        await self.repo.delete_category(category)
        