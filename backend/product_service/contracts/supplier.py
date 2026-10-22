"""Supplier-product payload fragments embedded in cross-service events."""

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from contracts.limits import (
    COUNT_MAX, Count, IMAGES_MAX, Identifier, Money, Name, OPTION_NAMES_MAX, SupplierText, Url, VARIANTS_MAX,
)




class SupplierProductVariant(BaseModel):
    vid: Identifier
    variant_key: Name | None = None
    variant_name_en: Name | None = None
    variant_sku: Identifier | None = None
    barcode: Identifier | None = None
    variant_image: Url | None = None
    # Grams and millimetres, as CJ gives them.
    variant_weight: Decimal | None = Field(default=None, ge=0, le=COUNT_MAX)
    variant_length: Count | None = None
    variant_width: Count | None = None
    variant_height: Count | None = None
    variant_sell_price: Money | None = None
    variant_sug_sell_price: Money | None = None
    inventory_num: Count | None = None


class GenericSupplierProduct(BaseModel):
    supplier_id: Identifier = Field(..., description="Stable supplier identifier.")
    supplier_pid: Identifier | None = None
    name: Name
    # The supplier's HTML, clipped; product-service turns it into bounded plain text.
    description: SupplierText | None = None
    sku: Identifier | None = None
    brand: Name = "cjdropshipping"
    price: Money
    quantity: Count = 0
    in_stock: bool = True
    image_url: Url | None = None
    images: list[Url] = Field(default_factory=list, max_length=IMAGES_MAX)
    supplier_category_id: Identifier | None = Field(
        default=None,
        description="Category identifier in the supplier catalog.",
    )
    category_name: Name | None = None
    variants: list[SupplierProductVariant] = Field(default_factory=list, max_length=VARIANTS_MAX)
    variant_option_names: list[Name] = Field(
        default_factory=list,
        max_length=OPTION_NAMES_MAX,
        description='What each part of a variant key names, in order: ["Color", "Size"] for "Black-XL".',
    )

    @field_validator("name", "brand", mode="after")
    @classmethod
    def to_lowercase(cls, value: str | None) -> str | None:
        return value.lower() if isinstance(value, str) else value


class SupplierStockKey(BaseModel):
    """A supplier product we sell and its variant ids: what a stock refresh asks the supplier about."""

    supplier_pid: Identifier
    vids: list[Identifier] = Field(max_length=VARIANTS_MAX)


class SupplierStockLevel(BaseModel):
    """
    Sellable stock of one supplier product, per variant id.

    Absolute numbers ("7 left"), already reduced by the safety buffer, so
    applying the same level twice is harmless.
    """

    supplier_pid: Identifier
    variants: dict[Identifier, int] = Field(default_factory=dict, max_length=VARIANTS_MAX)

    @field_validator("variants")
    @classmethod
    def _non_negative(cls, value: dict[str, int]) -> dict[str, int]:
        if any(quantity < 0 for quantity in value.values()):
            raise ValueError("stock cannot be negative")
        if any(quantity > COUNT_MAX for quantity in value.values()):
            raise ValueError(f"stock cannot be above {COUNT_MAX}")
        return value
