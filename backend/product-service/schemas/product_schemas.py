from datetime import datetime
from typing import Optional, List
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, PositiveInt, Field, ConfigDict

from schemas.review_schemas import ReviewSchema
from schemas.category_schema import CategorySchema



# --- Supporting Schemas ---

class ImageType(BaseModel):
    color: str = Field(..., min_length=3, max_length=50, description="Image color must be between 3 and 50 characters", example="Black")
    color_code: str = Field(..., min_length=3, max_length=50, description="Image color code must be between 3 and 50 characters" , example="#000000")
    image: str = Field(..., min_length=3, max_length=100, description="Image URL must be between 3 and 500 characters", example="https://example.com/image.jpg")

class CartImages(BaseModel):
    product_id: UUID 
    image_url: str = Field(..., min_length=3, max_length=100, description="Image URL must be between 3 and 500 characters", example="https://example.com/image.jpg")
    image_color_code: str = Field(..., min_length=3, max_length=50, description="Image color code must be between 3 and 50 characters" , example="#000000")
    id: UUID 
    image_color: str = Field(..., min_length=3, max_length=50, description="Image color must be between 3 and 50 characters", example="Black")



# --- Product Schemas ---

class ProductBase(BaseModel):
    """Base product schema with common attributes"""
    name: str = Field(..., min_length=3, max_length=50)
    description: str = Field(..., min_length=10, max_length=500)
    category_id: UUID
    brand: str = Field(..., min_length=3, max_length=50)
    quantity: PositiveInt = Field(..., gt=0, le=20)
    price: Decimal = Field(..., gt=0, le=100)
    in_stock: Optional[bool]

    model_config = ConfigDict(from_attributes=True)

class CreateProduct(ProductBase):
    """Schema for creating a product"""
    images: List[ImageType] = Field(..., min_items=1, max_items=5, description="List of product images with color and color code")

class UpdateProduct(ProductBase):
    """Schema for updating an existing product"""
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    brand: Optional[str] = None
    quantity: Optional[PositiveInt] = None
    price: Optional[Decimal] = None
    in_stock: Optional[bool] = None

class ProductSchema(ProductBase):
    """Schema for product responses"""
    id: UUID
    date_created: datetime
    date_updated: Optional[datetime] = None
    category: Optional[CategorySchema] = None
    selected_image: Optional[CartImages] = None
    images: List[CartImages]
    reviews: Optional[List[ReviewSchema]] = None

class CreatedProduct(ProductBase):
    id: UUID
    date_created: datetime
    date_updated: Optional[datetime] = None

class AllProducts(BaseModel):
    products: List[ProductSchema]

    model_config = ConfigDict(from_attributes=True)

# Optional: For query params etc
class ProductParams(BaseModel):
    category: Optional[str] = Field(None, min_length=3, max_length=50)
    searchTerm: Optional[str] = Field(None, min_length=3, max_length=50)