"""Supplier-product payload fragments embedded in cross-service events."""

from decimal import Decimal
from pydantic import BaseModel, Field, field_validator


class SupplierProductVariant(BaseModel):
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


class GenericSupplierProduct(BaseModel):
    supplier_id: str = Field(..., description="Stable supplier identifier.")
    supplier_pid: str | None = None
    name: str
    description: str | None = None
    sku: str | None = None
    brand: str = "cjdropshipping"
    price: Decimal
    quantity: int = 0
    in_stock: bool = True
    image_url: str | None = None
    images: list[str] = Field(default_factory=list)
    supplier_category_id: str | None = Field(
        default=None,
        description="Category identifier in the supplier catalog.",
    )
    category_name: str | None = None
    variants: list[SupplierProductVariant] = Field(default_factory=list)

    @field_validator("name", "brand", mode="after")
    @classmethod
    def to_lowercase(cls, value: str | None) -> str | None:
        return value.lower() if isinstance(value, str) else value
