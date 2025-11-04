from typing import Optional
from uuid import UUID

from fastapi import UploadFile

from models.category_models import ProductCategory
from exceptions.category_exceptions import CategoryNotFoundError, CategoryCreationError
from schemas.category_schema import CategorySchema, CreateCategory, UpdateCategory
from database_layer.category_repository import CategoryRepository
from utils.image_pathes import create_image_paths

class CategoryService:
    """Service layer for category management operations, business logic and data validation."""

    def __init__(self, repository: CategoryRepository):
        self.repository = repository

    async def create_category(self, name: str, image: UploadFile) -> CategorySchema:
        # Check if category already exists
        existing_category = await self.repository.get_by_field("name", value=name.lower())
        if existing_category:
            raise CategoryCreationError(f'Category with name: "{name}" already exists.')

        # Create image path
        image_paths = create_image_paths(images=[image])
        
        # Create new category
        new_category = ProductCategory(
            name=name.lower(),
            image_url=image_paths[0]
        )
        
        created_category = await self.repository.create(new_category)
        return CategorySchema.model_validate(created_category)
   
    async def get_all_categories(self) -> list[CategorySchema]:
        categories = await self.repository.get_all()
        if not categories or len(categories) == 0:
            raise CategoryNotFoundError("No categories found.")
        return [CategorySchema.model_validate(category) for category in categories]

    async def get_category_by_id(self, category_id: UUID) -> CategorySchema:
        category = await self.repository.get_by_id(item_id=category_id)
        if not category:
            raise CategoryNotFoundError(f'Category with id: "{category_id}" not found.')
        return CategorySchema.model_validate(category)
    
    async def get_category_by_name(self, name: str) -> CategorySchema:
        category = await self.repository.get_by_field("name", value=name.lower())
        if not category:
            raise CategoryNotFoundError(f'Category with name: "{name}" not found.')
        return CategorySchema.model_validate(category)

    async def update_category(self, 
                              category_id: UUID, 
                              name: Optional[str] = None, 
                              image: Optional[UploadFile] = None) -> CategorySchema:
        # Get only fields that were actually provided
        update_dict = {}
        if name is not None:
            update_dict['name'] = name.lower()
        if image is not None:
            image_paths = create_image_paths(images=[image])
            update_dict['image_url'] = image_paths[0]

        # Update category
        updated_category = await self.repository.update_by_id(category_id, **update_dict)
        if not updated_category:
            raise CategoryNotFoundError(f"Category with id: {category_id} not found.")

        return CategorySchema.model_validate(updated_category)

    async def delete_category(self, category_id: UUID) -> None:
        success = await self.repository.delete_by_id(category_id)
        if not success:
            raise CategoryNotFoundError(f"Category id: {category_id} not found")
        