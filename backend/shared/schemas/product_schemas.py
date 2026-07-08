from typing import Optional
from datetime import datetime
from decimal import Decimal
from typing import List
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from fastapi import UploadFile, Form, File

from shared.schemas.category_schema import CategorySchema
from shared.schemas.product_image_schema import ImageType
from shared.schemas.review_schemas import ReviewSchema


# --- Product Variant Schemas ---

class ProductVariantBase(BaseModel):
    """Base schema for product variants."""

    id: UUID
    product_id: UUID
    vid: str
    variant_key: str | None = None
    variant_name_en: str | None = None
    variant_sku: str | None = None
    barcode: str | None = None
    variant_image: str | None = None
    variant_weight: Decimal | None = None
    variant_length: int | None = None
    variant_width: int | None = None
    variant_height: int | None = None
    variant_sell_price: Decimal | None = None
    variant_sug_sell_price: Decimal | None = None
    inventory_num: int | None = None
    date_created: datetime
    date_updated: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CreateProductVariant(BaseModel):
    """Schema for creating a product variant."""

    vid: str
    variant_key: str | None = None
    variant_name_en: str | None = None
    variant_sku: str | None = None
    barcode: str | None = None
    variant_image: str | None = None
    variant_weight: Decimal | None = None
    variant_length: int | None = None
    variant_width: int | None = None
    variant_height: int | None = None
    variant_sell_price: Decimal | None = None
    variant_sug_sell_price: Decimal | None = None
    inventory_num: int | None = None


# --- Product Schemas ---

class BaseFilters(BaseModel):
    # Pagination
    offset: int = Field(default=0, ge=0, description="Number of records to skip")
    limit: int = Field(default=10, gt=0, le=100, description="Maximum number of records to return")

    # Sorting
    sort_order: Optional[str] = Field(None, pattern="^(asc|desc)$")


class ProductBase(BaseModel):
    """Base product schema with common attributes"""

    id: UUID
    pid: str | None = None
    name: str = Field(..., min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category_id: UUID
    brand: str = Field(..., min_length=1, max_length=50)
    quantity: int
    price: Decimal = Field(..., gt=0, le=99999)
    in_stock: bool
    sku: str | None = None
    image_url: str | None = None
    date_created: datetime
    date_updated: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ProductUploadForm(BaseModel):
    name: str
    description: str
    category_id: UUID
    brand: str
    quantity: int
    price: Decimal
    in_stock: bool
    images: list[UploadFile]
    image_colors: list[str]
    image_color_codes: list[str]

    # automaticaly handling lowercasing
    @field_validator('name', "brand", mode='after')
    @classmethod
    def to_lowercase(cls, value: str) -> str:
        return value.lower()

    @classmethod
    def return_as_form(cls,
                       name: str = Form(...),
                       description: str = Form(...),
                       category_id: UUID = Form(...),
                       brand: str = Form(...),
                       quantity: int = Form(...),
                       price: Decimal = Form(...),
                       in_stock: bool = Form(...),
                       images: list[UploadFile] = File(...),
                       image_colors: list[str] = Form(...),
                       image_color_codes: list[str] = Form(...)):
        return cls(
            name=name,
            description=description,
            category_id=category_id,
            brand=brand,
            quantity=quantity,
            price=price,
            in_stock=in_stock,
            images=images,
            image_colors=image_colors,
            image_color_codes=image_color_codes,
        )


class CreateProduct(BaseModel):
    """Schema for creating a product"""

    id: UUID | str | None = Field(default_factory=lambda: uuid4())
    pid: str | None = None
    name: str = Field(..., min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category_id: UUID | str | None
    brand: str = Field(default="cjdropshipping", min_length=1, max_length=50)
    quantity: int = Field(..., ge=0, le=1000000)
    price: Decimal = Field(..., gt=0, le=9000)
    in_stock: bool
    sku: str | None = Field(default=None, max_length=70)
    image_url: str | None = None
    variants: list[CreateProductVariant] | None = None
    images: list[str] | None = None

    @field_validator("name", "brand", mode="after")
    @classmethod
    def to_lowercase(cls, value: str) -> str:
        return value.lower()

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
    quantity: Optional[int] = Field(None, ge=0)
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
    variants: List[ProductVariantBase] = []


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


class CJDropshippingFilterParams(BaseModel):
    keyWord: str = Field(description="Product name or SKU keyword search")
    page: int = Field(description="Default 1, minimum 1, maximum 1000")
    size: int = Field(description="Default 10, minimum 1, maximum 100")
    categoryId: str = Field(description="Filter products by third level category ID")
    countryCode: str = Field(description="Format: CN,US,GB,FR etc., filter products with inventory in specified countries")


class CJProductPreview(BaseModel):
    """Lightweight preview of a CJ Dropshipping product from the list endpoint."""

    pid: str
    name: str
    sku: str | None = None
    image_url: str | None = None
    price: Decimal
    quantity: int
    in_stock: bool
    category_id: str | None = None


class CustomTshirtPricingResponse(BaseModel):
    base_price: float = Field(..., ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
