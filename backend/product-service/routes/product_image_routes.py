from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from database.connection import get_db_session
from service_layer.product_image_service import ProductImageService
from schemas.product_schemas import ProductImageSchema, CreateProductImage

product_images_routes = APIRouter(tags=["product_images"])

@product_images_routes.post("/{product_id}/images", response_model=List[ProductImageSchema])
async def add_product_images(product_id: UUID,
                             images: List[CreateProductImage], 
                             db: AsyncSession = Depends(get_db_session)):
    
    image_service = ProductImageService(db)
    return await image_service.create_product_images(product_id, images)

@product_images_routes.get("/{product_id}/images", response_model=List[ProductImageSchema])
async def get_product_images(
    product_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Get all images for a product"""
    image_service = ProductImageService(db)
    return await image_service.get_product_images(product_id)

@product_images_routes.put("/{product_id}/images", response_model=List[ProductImageSchema])
async def replace_product_images(
    product_id: UUID,
    images: List[CreateProductImage],
    db: AsyncSession = Depends(get_db_session)
):
    """Replace all images for a product"""
    image_service = ProductImageService(db)
    return await image_service.replace_product_images(product_id, images)

@product_images_routes.delete("/{product_id}/images/{image_id}")
async def delete_product_image(
    product_id: UUID,
    image_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Delete a specific product image"""
    image_service = ProductImageService(db)
    await image_service.delete_product_image(image_id)
    return {"message": "Image deleted successfully"}