"""Generic supplier product schemas.

These models decouple supplier-specific APIs (CJDropshipping, etc.) from the
product_service. A supplier_service fetches raw products, maps them to these
generic schemas, and emits ``SupplierProductsFetched`` events. The
product_service consumes those events and maps them to its own ``CreateProduct``
schema.
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SupplierProductVariant(BaseModel):
    """Generic variant representation from any supplier."""

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
    """Normalized product representation emitted by supplier_service.

    Fields mirror ``shared.schemas.product_schemas.CreateProduct`` but keep the
    supplier's original category identifier so product_service can resolve it.
    """

    supplier_id: str = Field(..., description="Stable identifier for the supplier, e.g. 'cjdropshipping'.")
    supplier_pid: str | None = Field(default=None, description="Supplier's own product id.")
    name: str
    description: str | None = None
    sku: str | None = None
    brand: str = "cjdropshipping"
    price: Decimal
    quantity: int = 0
    in_stock: bool = True
    image_url: str | None = None
    images: list[str] = Field(default_factory=list)
    category_id: str | UUID | None = Field(
        default=None,
        description="Supplier category id or existing product_service category UUID.",
    )
    category_name: str | None = Field(default=None, description="Human-readable category name for auto-creation.")
    variants: list[SupplierProductVariant] = Field(default_factory=list)

    @field_validator("name", "brand", mode="after")
    @classmethod
    def to_lowercase(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.lower()
        return value


class SupplierProductsPage(BaseModel):
    """Paginated result returned by a SupplierProvider.search_products call."""

    page: int
    page_size: int
    total_records: int | None = None
    total_pages: int | None = None
    products: list[GenericSupplierProduct]


class SupplierConfigBase(BaseModel):
    """Minimal supplier configuration schema used across services."""

    supplier_id: str
    name: str
    provider_type: str = Field(default="cjdropshipping", description="Provider implementation key.")
    is_active: bool = True
    sync_interval_minutes: int = Field(default=60, ge=1)
    default_category_name: str | None = None
    config: dict = Field(default_factory=dict, description="Provider-specific JSON config.")


class SupplierSyncRunSummary(BaseModel):
    """Result of a single supplier sync run."""

    supplier_id: str
    fetch_id: UUID
    started_at: datetime
    finished_at: datetime | None = None
    products_fetched: int = 0
    products_emitted: int = 0
    errors: list[str] = Field(default_factory=list)
    status: str = "pending"

    model_config = ConfigDict(from_attributes=True)
