from typing import List, Optional
from uuid import UUID

from fastapi import UploadFile

from database_layer.product_image_repository import ProductImageRepository
from exceptions.product_image_exceptions import (
    ProductImageNotFoundError,
    ProductImageProcessingError,
)
from models.product_image_models import ProductImage
from schemas.product_image_schema import ImageType, ProductImageSchema
from utils.image_processing import image_processing_manager


class ProductImageService:
    """Service layer for product image management operations."""

    def __init__(self, repository: ProductImageRepository):
        self.repository = repository
        self.product_image_relations = ProductImage.get_relations()
        self.product_image_search_fields = ProductImage.get_search_fields()

    # ---------- create ----------

    async def create_product_images(
        self,
        product_id: UUID,
        images: List[ImageType],
    ) -> List[ProductImageSchema]:
        """Create multiple product images for a product"""

        product_images = [
            ProductImage(
                product_id=product_id,
                image_url=image.image_url,
                image_color=image.image_color,
                image_color_code=image.image_color_code,
            )
            for image in images
        ]

        created_images = await self.repository.create_many(product_images)
        return [ProductImageSchema.model_validate(img) for img in created_images]

    # ---------- read ----------

    async def get_images(self) -> List[ProductImageSchema]:
        images = await self.repository.get_all()
        return [ProductImageSchema.model_validate(img) for img in images]

    async def get_product_images(self, product_id: UUID) -> List[ProductImageSchema]:
        images = await self.repository.get_many_by_field(
            field_name="product_id",
            value=product_id,
        )
        return [ProductImageSchema.model_validate(img) for img in images]

    async def get_image_by_id(self, image_id: UUID) -> ProductImageSchema:
        image = await self.repository.get_by_id(image_id)
        if not image:
            raise ProductImageNotFoundError(
                f"Product image with id {image_id} not found"
            )
        return ProductImageSchema.model_validate(image)

    # ---------- update ----------

    async def update_product_image(
        self,
        image_id: UUID,
        *,
        image_url: Optional[str] = None,
        color: Optional[str] = None,
        color_code: Optional[str] = None,
    ) -> ProductImageSchema:
        """Update image fields only (no file handling here)"""

        update_data = {}

        if image_url is not None:
            update_data["image_url"] = image_url
        if color is not None:
            update_data["image_color"] = color
        if color_code is not None:
            update_data["image_color_code"] = color_code

        if not update_data:
            raise ProductImageProcessingError("No fields provided for update")

        updated_image = await self.repository.update_by_id(
            image_id,
            **update_data,
        )

        if not updated_image:
            raise ProductImageNotFoundError(
                f"Product image with id {image_id} not found"
            )

        return ProductImageSchema.model_validate(updated_image)

    async def update_product_image_with_file(
        self,
        image_id: UUID,
        *,
        image: Optional[UploadFile] = None,
        image_color: Optional[str] = None,
        image_color_code: Optional[str] = None,
    ) -> ProductImageSchema:
        """
        Composite update:
        - optionally saves new image file
        - updates metadata
        """

        image_url: Optional[str] = None

        if image:
            image_url = await image_processing_manager.save_image(image)

        return await self.update_product_image(
            image_id=image_id,
            image_url=image_url,
            color=image_color,
            color_code=image_color_code,
        )

    # ---------- delete ----------

    async def delete_product_image(self, image_id: UUID) -> None:
        success = await self.repository.delete_by_id(image_id)
        if not success:
            raise ProductImageNotFoundError(
                f"Product image with id {image_id} not found"
            )

    async def delete_all_product_images(self, product_id: UUID) -> int:
        return await self.repository.delete_many_by_field(
            field_name="product_id",
            value=product_id,
        )

    # ---------- replace ----------

    async def replace_product_images(
        self,
        product_id: UUID,
        new_images: List[ImageType],
    ) -> List[ProductImageSchema]:
        """Replace all images for a product"""

        await self.delete_all_product_images(product_id)
        return await self.create_product_images(product_id, new_images)
