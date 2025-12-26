from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator
from shared.schemas.product_schemas import BaseFilters  # type: ignore

from schemas.category_schema import CategorySchema
from schemas.product_image_schema import ImageType
from schemas.review_schemas import ReviewSchema

# --- Product Schemas ---


class ProductBase(BaseModel):
    """Base product schema with common attributes"""

    id: UUID
    name: str = Field(..., min_length=3, max_length=50)
    description: str = Field(..., min_length=10, max_length=500)
    category_id: UUID
    brand: str = Field(..., min_length=3, max_length=50)
    quantity: int
    price: Decimal = Field(..., gt=0, le=100)
    in_stock: bool
    date_created: datetime
    date_updated: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CreateProduct(BaseModel):
    """Schema for creating a product"""

    name: str = Field(..., min_length=3, max_length=50)
    description: str = Field(..., min_length=10, max_length=500)
    category_id: UUID
    brand: str = Field(..., min_length=3, max_length=50)
    quantity: PositiveInt = Field(..., gt=0, le=100)
    price: Decimal = Field(..., gt=0, le=100)
    in_stock: bool

    @field_validator("in_stock", mode="before")
    @classmethod
    def convert_in_stock(cls, value: str):
        if isinstance(value, str):
            if value.lower() == "true":
                return True
            elif value.lower() == "false":
                return False
        return value


class UpdateProduct(BaseModel):
    """Schema for updating an existing product"""

    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    brand: Optional[str] = None
    quantity: Optional[PositiveInt] = None
    price: Optional[Decimal] = None
    in_stock: Optional[bool] = None

    @field_validator("in_stock", mode="before")
    @classmethod
    def convert_in_stock(cls, v: str):
        if isinstance(v, str):
            if v.lower() == "true":
                return True
            elif v.lower() == "false":
                return False
        return v


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


class ProductsFilterParams(BaseFilters):
    # Sorting options
    sort_by: Optional[str] = Field(
        None, pattern="^(name|price|date_created|date_updated|quantity)$"
    )

    # Filtering options
    name: Optional[str] = None
    brand: Optional[str] = None
    category_id: Optional[UUID] = None
    search_term: Optional[str] = Field(None, min_length=3, max_length=50)
    in_stock: Optional[bool] = None

    # Price filters (exact and range)
    price: Optional[Decimal] = None  # Exact price match
    min_price: Optional[Decimal] = Field(None, ge=0)
    max_price: Optional[Decimal] = Field(None, ge=0)

    # Quantity filters (exact and range)
    quantity: Optional[int] = None  # Exact quantity match
    min_quantity: Optional[int] = Field(None, ge=0)
    max_quantity: Optional[int] = Field(None, ge=0)

    # Date range filters
    date_created_from: Optional[datetime] = None
    date_created_to: Optional[datetime] = None
    date_updated_from: Optional[datetime] = None
    date_updated_to: Optional[datetime] = None

    @field_validator("in_stock", mode="before")
    @classmethod
    def convert_in_stock(cls, value):
        """Convert string 'true'/'false' to boolean"""
        if value is None:
            return None
        if isinstance(value, str):
            return value.lower() == "true"
        return value

    @field_validator(
        "date_created_from",
        "date_created_to",
        "date_updated_from",
        "date_updated_to",
        mode="before",
    )
    @classmethod
    def parse_datetime(cls, value):
        """Parse ISO datetime strings"""
        if value is None:
            return None
        if isinstance(value, str):
            try:
                # Handle ISO format with 'Z' suffix
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return value
