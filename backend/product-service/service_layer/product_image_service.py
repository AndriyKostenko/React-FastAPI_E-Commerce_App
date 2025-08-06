from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from models.product_image_models import ProductImage
from schemas.product_image_schema import ProductImageSchema
from database_layer.product_image_repository import ProductImageRepository
from errors.product_image_errors import ProductImageNotFoundError, ProductImageAlreadyExistsError


class ProductImageService:
    """Service layer for product image management operations."""
    
    def __init__(self, repository: ProductImageRepository):
        self.repository = repository

    async def create_product_images(self, product_id: UUID, images: list) -> List[ProductImageSchema]:
        """Create multiple product images for a product"""
        existing_images = await self.repository.get_many_by_field(field_name="product_id", value=product_id)
        if existing_images:
            raise ProductImageAlreadyExistsError(f"Product with id: {product_id} already has images associated with it.")
            
        product_images = [
            ProductImage(
                product_id=product_id,
                image_url=image.image_url,
                image_color=image.image_color,
                image_color_code=image.image_color_code
            ) 
            for image in images
        ]

        created_images = await self.repository.create_many(product_images)
        return [ProductImageSchema.model_validate(img) for img in created_images]

    async def get_product_images(self, product_id: UUID) -> List[ProductImageSchema]:
        """Get all images for a specific product"""
        images = await self.repository.get_many_by_field(field_name="product_id", value=product_id)
        return [ProductImageSchema.model_validate(img) for img in images]
    
    async def get_image_by_id(self, image_id: UUID) -> ProductImageSchema:
        """Get a specific product image by ID"""
        image = await self.repository.get_by_id(image_id)
        if not image:
            raise ProductImageNotFoundError(f"Product image with id: {image_id} not found")
        return ProductImageSchema.model_validate(image)

    async def update_product_image(self, image_id: UUID, **kwargs) -> ProductImageSchema:
        """Update a product image"""
        updated_image = await self.repository.update_by_id(image_id, **kwargs)
        if not updated_image:
            raise ProductImageNotFoundError(f"Product image with id: {image_id} not found")
        return ProductImageSchema.model_validate(updated_image)

    async def delete_product_image(self, image_id: UUID) -> None:
        """Delete a specific product image"""
        success = await self.repository.delete_by_id(image_id)
        if not success:
            raise ProductImageNotFoundError(f"Product image with id: {image_id} not found")

    async def delete_all_product_images(self, product_id: UUID) -> int:
        """Delete all images for a specific product"""
        return await self.repository.delete_many_by_field(field_name="product_id", value=product_id)

    async def replace_product_images(self, product_id: UUID, new_images: list) -> List[ProductImageSchema]:
        """Replace all images for a product with new ones"""
        # Delete existing images
        await self.delete_all_product_images(product_id)
        
        # Create new images
        return await self.create_product_images(product_id, new_images)