from typing import Optional
from uuid import UUID

from fastapi import UploadFile
from pydantic import HttpUrl

from database_layer.category_repository import CategoryRepository
from exceptions.category_exceptions import CategoryCreationError, CategoryNotFoundError
from models.category_models import ProductCategory
from shared.schemas.category_schema import CategorySchema, CreateCategory, UpdateCategory
from utils.image_processing import image_processing_manager


class CategoryService:
    """Service layer for category management operations, business logic and data validation."""

    def __init__(self, repository: CategoryRepository, default_category_name: str = "cjdropshipping"):
        self.repository: CategoryRepository = repository
        self.default_category_name: str = default_category_name

    async def create_category(self,
                              category_data: CreateCategory,
                              image: UploadFile | None = None) -> CategorySchema:
        # Check if category already exists
        existing_category = await self.repository.get_by_field(
            "name", category_data.name.lower()
        )
        if existing_category:
            raise CategoryCreationError(
                f'Category with name: "{category_data.name}" already exists.'
            )

        # Determine image URL: uploaded image takes priority, else use provided URL
        image_url: HttpUrl | str | None = category_data.image_url
        if image:
            image_url = await image_processing_manager.save_icon(image)

        # Create category
        new_category = ProductCategory(
            name=category_data.name.lower(),
            cj_category_id=category_data.cj_category_id,
            image_url=image_url,
        )

        created_category = await self.repository.create(new_category)
        return CategorySchema.model_validate(created_category)

    async def get_or_create_by_cj_id(self, cj_category_id: str | None, name: str | None = None) -> UUID:
        """Look up a local category by CJ category ID, creating one if needed.

        Returns the local category UUID. Falls back to a default 'cjdropshipping'
        category when no CJ category ID is provided.
        """
        if not cj_category_id:
            default_name = self.default_category_name.lower().strip()
            default_category = await self.repository.get_by_field("name", default_name)
            if default_category:
                return default_category.id
            new_category = ProductCategory(name=default_name, cj_category_id=None)
            created = await self.repository.create(new_category)
            return created.id

        existing = await self.repository.get_by_field("cj_category_id", cj_category_id)
        if existing:
            return existing.id

        category_name = (name or cj_category_id).lower().strip()
        # Ensure uniqueness of the local name
        name_candidate = category_name
        suffix = 1
        while await self.repository.get_by_field("name", name_candidate):
            name_candidate = f"{category_name}-{suffix}"
            suffix += 1

        new_category = ProductCategory(
            name=name_candidate,
            cj_category_id=cj_category_id,
        )
        created = await self.repository.create(new_category)
        return created.id

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

    async def update_category(
        self,
        category_id: UUID,
        name: Optional[str] = None,
        image: Optional[UploadFile] = None,
    ) -> CategorySchema:
        # Get only fields that were actually provided
        update_dict = {}
        if name is not None:
            update_dict["name"] = name.lower()
        if image is not None:
            image_paths = await image_processing_manager.save_icon(image)
            update_dict["image_url"] = image_paths[0]

        # Update category
        updated_category = await self.repository.update_by_id(
            category_id, data=update_dict
        )
        if not updated_category:
            raise CategoryNotFoundError(f"Category with id: {category_id} not found.")

        return CategorySchema.model_validate(updated_category)

    async def delete_category(self, category_id: UUID) -> None:
        success = await self.repository.delete_by_id(category_id)
        if not success:
            raise CategoryNotFoundError(f"Category id: {category_id} not found")
