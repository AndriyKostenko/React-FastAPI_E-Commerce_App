from datetime import datetime
from typing import Optional, List
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, PositiveInt, Field, ConfigDict, HttpUrl

from schemas.review_schemas import ReviewSchema
from schemas.category_schema import CategorySchema
from schemas.product_image_schema import ImageType




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
    ...

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

    reviews: Optional[List[ReviewSchema]] = None
    category: Optional[CategorySchema] = None
    images: List[ImageType]

class CreatedProduct(ProductBase):
    id: UUID
    date_created: datetime
    date_updated: Optional[datetime] = None
    
class ProductsFilterParams(BaseModel):
    # Pagination
    offset: int = Field(default=0, ge=0, description="Number of records to skip")
    limit: int = Field(default=10, gt=0, le=100, description="Maximum number of records to return")
    
    # Sorting options
    sort_by: Optional[str] = Field(None, pattern="^(name|price|date_created|date_updated|quantity)$")
    sort_order: Optional[str] = Field(None, pattern="^(asc|desc)$")
    
    # Filtering options
    category: Optional[str] = None
    search_term: Optional[str] = Field(None, min_length=3, max_length=50)
    
    # Date range filters
    date_created_from: Optional[datetime] = Field(None, description="Filter users created from this date")
    date_created_to: Optional[datetime] = Field(None, description="Filter users created up to this date")
    date_updated_from: Optional[datetime] = Field(None, description="Filter users updated from this date")
    date_updated_to: Optional[datetime] = Field(None, description="Filter users updated up to this date")
    