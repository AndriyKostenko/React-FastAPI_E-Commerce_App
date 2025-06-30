from datetime import datetime
from typing import Optional, List
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, PositiveInt, Field, ConfigDict, HttpUrl

from schemas.review_schemas import ReviewSchema
from schemas.category_schema import CategorySchema



# --- Supporting Schemas ---

class ImageType(BaseModel):
    image_color: str = Field(..., min_length=3, max_length=50, description="Image color must be between 3 and 50 characters", example="Black")
    image_color_code: str = Field(..., min_length=3, max_length=50, description="Image color code must be between 3 and 50 characters" , example="#000000")
    image_url: str

    model_config = ConfigDict(from_attributes=True)

class CartImages(BaseModel):
    product_id: UUID 
    image_url: str
    image_color_code: str = Field(..., min_length=3, max_length=50, description="Image color code must be between 3 and 50 characters" , example="#000000")
    id: UUID 
    image_color: str = Field(..., min_length=3, max_length=50, description="Image color must be between 3 and 50 characters", example="Black")

    model_config = ConfigDict(from_attributes=True)

# --- Product Schemas ---

class ProductBase(BaseModel):
    """Base product schema with common attributes"""
    name: str = Field(..., min_length=3, max_length=50)
    description: str = Field(..., min_length=10, max_length=500)
    category_id: UUID
    brand: str = Field(..., min_length=3, max_length=50)
    quantity: PositiveInt = Field(..., gt=0, le=20)
    price: Decimal = Field(..., gt=0, le=100)
    in_stock: bool

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
    category: Optional[CategorySchema] = None
    images: List[ImageType]
    date_created: datetime
    date_updated: Optional[datetime] = None
    
    reviews: Optional[List[ReviewSchema]] = None

class CreatedProduct(ProductBase):
    id: UUID
    date_created: datetime
    date_updated: Optional[datetime] = None
    
    
class ProductParams(BaseModel):
    category: Optional[str] = Field(None, min_length=3, max_length=50)
    searchTerm: Optional[str] = Field(None, min_length=3, max_length=50)