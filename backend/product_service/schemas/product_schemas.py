from typing import Annotated, Optional, Literal
from datetime import datetime
from decimal import Decimal
from typing import List
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from fastapi import UploadFile, Form, File

from contracts.limits import (
    COUNT_MAX, IMAGES_MAX, NAME_MAX_LENGTH, VARIANTS_MAX, Code, Count, Identifier, Money, Name, Url,
)
from schemas.category_schema import CategorySchema
from schemas.product_image_schema import ProductImageView
from schemas.review_schemas import ReviewSchema
from storage.catalogue_url import CatalogueImageUrl


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
    variant_image: CatalogueImageUrl | None = None
    variant_weight: Decimal | None = None
    variant_length: int | None = None
    variant_width: int | None = None
    variant_height: int | None = None
    variant_sell_price: Decimal | None = None
    variant_sug_sell_price: Decimal | None = None
    retail_price: Decimal | None = None
    inventory_num: int | None = None
    active: bool = True
    date_created: datetime
    date_updated: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CreateProductVariant(BaseModel):
    """Schema for creating a product variant."""

    vid: Identifier
    variant_key: Name | None = None
    variant_name_en: Name | None = None
    variant_sku: Identifier | None = None
    barcode: Identifier | None = None
    variant_image: Url | None = None
    variant_weight: Decimal | None = Field(default=None, ge=0, le=COUNT_MAX)
    variant_length: Count | None = None
    variant_width: Count | None = None
    variant_height: Count | None = None
    variant_sell_price: Money | None = None
    variant_sug_sell_price: Money | None = None
    retail_price: Money | None = None
    inventory_num: Count | None = None


# --- Product Schemas ---

class BaseFilters(BaseModel):
    # Pagination
    offset: int = Field(default=0, ge=0, le=COUNT_MAX, description="Number of records to skip")
    limit: int = Field(default=10, gt=0, le=100, description="Maximum number of records to return")

    # Sorting
    sort_order: Optional[str] = Field(None, pattern="^(asc|desc)$")


class ProductBase(BaseModel):
    """Base product schema with common attributes"""

    id: UUID
    pid: str | None = None
    supplier_id: str | None = None
    name: str = Field(..., min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category_id: UUID
    brand: str = Field(..., min_length=1, max_length=50)
    quantity: int
    price: Decimal = Field(..., gt=0, le=99999)
    in_stock: bool
    sku: str | None = None
    image_url: CatalogueImageUrl | None = None
    date_created: datetime
    date_updated: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ProductUploadForm(BaseModel):
    # The same bounds as CreateProduct.
    name: str = Field(min_length=3, max_length=200)
    description: str = Field(max_length=2000)
    category_id: UUID
    brand: str = Field(min_length=1, max_length=50)
    quantity: Count
    price: Decimal = Field(gt=0, le=9000)
    in_stock: bool
    images: list[UploadFile] = Field(max_length=IMAGES_MAX)
    image_colors: list[Name] = Field(max_length=IMAGES_MAX)
    image_color_codes: list[Code] = Field(max_length=IMAGES_MAX)

    # automaticaly handling lowercasing
    @field_validator('name', "brand", mode='after')
    @classmethod
    def to_lowercase(cls, value: str) -> str:
        return value.lower()

    @classmethod
    def return_as_form(cls,
                       name: str = Form(..., min_length=3, max_length=200),
                       description: str = Form(..., max_length=2000),
                       category_id: UUID = Form(...),
                       brand: str = Form(..., min_length=1, max_length=50),
                       quantity: int = Form(..., ge=0, le=COUNT_MAX),
                       price: Decimal = Form(..., gt=0, le=9000),
                       in_stock: bool = Form(...),
                       images: list[UploadFile] = File(..., max_length=IMAGES_MAX),
                       image_colors: list[Name] = Form(..., max_length=IMAGES_MAX),
                       image_color_codes: list[Code] = Form(..., max_length=IMAGES_MAX)):
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

    id: UUID | Identifier | None = Field(default_factory=lambda: uuid4())
    pid: Identifier | None = None
    supplier_id: str | None = Field(default=None, max_length=100)
    supplier_category_id: str | None = Field(default=None, max_length=200)
    name: str = Field(..., min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category_id: UUID
    brand: str = Field(default="cjdropshipping", min_length=1, max_length=50)
    quantity: int = Field(..., ge=0, le=COUNT_MAX)
    price: Decimal = Field(..., gt=0, le=9000)
    in_stock: bool
    sku: str | None = Field(default=None, max_length=70)
    image_url: Url | None = None
    variants: list[CreateProductVariant] | None = Field(default=None, max_length=VARIANTS_MAX)
    variant_option_names: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(
        default_factory=list, max_length=5
    )
    images: list[Url] | None = Field(default=None, max_length=IMAGES_MAX)

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

    # The same bounds as CreateProduct.
    name: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    category_id: Optional[UUID] = None
    brand: Optional[str] = Field(None, min_length=1, max_length=50)
    quantity: Optional[int] = Field(None, ge=0, le=COUNT_MAX)
    price: Optional[Decimal] = Field(None, gt=0, le=9000)
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
    images: List[ProductImageView]
    variants: List[ProductVariantBase] = []
    # Names the parts of each variant_key, in order ("Color", "Size").
    variant_option_names: list[str] = []


# --- Product Card Schemas ---
#
# GET /products/cards lists the whole shop in one call, so each product carries
# only what a shop card, its tabs (rating, date) and its filters (price, variant
# colour and size) read: about 1.5 KB instead of the ~20 KB of ProductSchema.
# The filters read each key through the product's variant_option_names, so a
# "Size-Color" key ("M-Red") gives its size as well as its colour.

class ProductCardCategory(BaseModel):
    id: UUID
    name: str


class ProductCardReview(BaseModel):
    rating: float = Field(..., ge=0, le=5)


class ProductCardVariant(BaseModel):
    """An active variant's key ("Black-XL"); the filters read its colour and size."""

    variant_key: str | None = None
    active: Literal[True] = True


class ProductCardSchema(BaseModel):
    id: UUID
    supplier_id: str | None = None
    name: str
    price: Decimal
    in_stock: bool
    image_url: CatalogueImageUrl | None = None
    date_created: datetime
    category: ProductCardCategory
    reviews: list[ProductCardReview]
    variants: list[ProductCardVariant]
    # Names the parts of each variant_key, in order ("Size", "Color").
    variant_option_names: list[str] = []


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
    name: Optional[str] = Field(None, max_length=NAME_MAX_LENGTH)
    brand: Optional[str] = Field(None, max_length=NAME_MAX_LENGTH)
    category_id: Optional[UUID] = None
    search_term: Optional[str] = Field(None, min_length=3, max_length=50)
    in_stock: Optional[bool] = None

    # Price filters (exact and range)
    price: Optional[Money] = None  # Exact price match
    min_price: Optional[Money] = None
    max_price: Optional[Money] = None

    # Quantity filters (exact and range)
    quantity: Optional[Count] = None  # Exact quantity match
    min_quantity: Optional[Count] = None
    max_quantity: Optional[Count] = None

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


class ProductCardsFilterParams(ProductsFilterParams):
    # The shop loads every card at once (the CJ sync keeps about 200 products).
    limit: int = Field(default=500, gt=0, le=500, description="Maximum number of records to return")


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


class OrderQuoteLineRequest(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    quantity: int = Field(gt=0, le=99)


class OrderQuoteRequest(BaseModel):
    items: list[OrderQuoteLineRequest] = Field(min_length=1, max_length=50)


class OrderQuoteLine(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    product_name: str
    quantity: int
    unit_price: Decimal
    fulfillment_type: Literal["catalog", "cj"]
    supplier_id: str | None = None
    variant_snapshot: dict | None = None


class OrderQuoteResponse(BaseModel):
    currency: str = "CAD"
    items: list[OrderQuoteLine]
    total_amount: Decimal
