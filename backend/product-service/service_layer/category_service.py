from uuid import UUID

from models.category_models import ProductCategory
from exceptions.category_exceptions import CategoryNotFoundError, CategoryCreationError
from schemas.category_schema import CategorySchema, CreateCategory, UpdateCategory
from database_layer.category_repository import CategoryRepository


class CategoryService:
    """Service layer for category management operations, business logic and data validation."""

    def __init__(self, repository: CategoryRepository):
        self.repository = repository

    async def create_category(self, category_data: CreateCategory) -> CategorySchema:
        db_category = await self.repository.get_by_field("name", value=category_data.name.lower())
        if db_category:
            raise CategoryCreationError(f'Category with name: "{category_data.name}" already exists.')
        new_category = ProductCategory(name=category_data.name.lower(), 
                                       image_url=category_data.image_url)
        new_db_category = await self.repository.create(new_category)
        return CategorySchema.model_validate(new_db_category)
   
    async def get_all_categories(self) -> list[CategorySchema]:
        categories = await self.repository.get_all()
        if not categories or len(categories) == 0:
            raise CategoryNotFoundError("No categories found.")
        return [CategorySchema.model_validate(category) for category in categories]

    async def get_category_by_id(self, category_id: UUID) -> CategorySchema:
        category = await self.repository.get_by_id(id=category_id)
        if not category:
            raise CategoryNotFoundError(f'Category with id: "{category_id}" not found.')
        return CategorySchema.model_validate(category)
    
    async def get_category_by_name(self, name: str) -> CategorySchema:
        category = await self.repository.get_by_field("name", value=name.lower())
        if not category:
            raise CategoryNotFoundError(f'Category with name: "{name}" not found.')
        return CategorySchema.model_validate(category)

    async def update_category(self, category_id: UUID, data: UpdateCategory) -> CategorySchema:
        # Converting Pydantic model to dictionary
        update_fields = {key: value for key, value in data.model_dump().items() if value is not None}
        
        updated_category = await self.repository.update_by_id(category_id, **update_fields)
        if not updated_category:
            raise CategoryNotFoundError(f"Category id: {category_id} not found")
        return CategorySchema.model_validate(updated_category)

    async def delete_category(self, category_id: UUID) -> None:
        success = await self.repository.delete_by_id(category_id)
        if not success:
            raise CategoryNotFoundError(f"Category id: {category_id} not found")
        