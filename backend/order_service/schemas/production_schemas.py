from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt

from shared.enums.status_enums import ProductionJobStatus


class PrintSpecification(BaseModel):
    """The server-measured production facts the operator prints from."""

    size: str
    garment_color: str
    gender: str
    placement: str
    style: str
    prompt: str
    print_width_in: PositiveFloat | None = None
    print_height_in: PositiveFloat | None = None
    effective_dpi: PositiveFloat | None = None
    artwork_key: str
    artwork_sha256: str
    artwork_width_px: PositiveInt
    artwork_height_px: PositiveInt


class ProductionJobSchema(BaseModel):
    """One row of the operator's work queue."""

    id: UUID
    order_id: UUID
    order_item_id: UUID
    status: ProductionJobStatus
    quantity: int
    customer_email: str | None = None
    product_name: str | None = None
    tracking_number: str | None = None
    carrier: str | None = None
    tracking_url: str | None = None
    notes: str | None = None
    reconciliation_required: bool = False
    cancellation_reason: str | None = None
    print_specification: PrintSpecification | None = None
    date_created: datetime
    started_at: datetime | None = None
    printed_at: datetime | None = None
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    cancelled_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ProductionQueuePage(BaseModel):
    """A page of the queue plus the counts the dashboard header shows."""

    items: list[ProductionJobSchema]
    total: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class StartProductionJobRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class MarkPrintedRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class ShipProductionJobRequest(BaseModel):
    """Dispatch details entered by the operator when the parcel is posted."""

    tracking_number: str = Field(min_length=3, max_length=100)
    carrier: str | None = Field(default=None, max_length=100)
    tracking_url: str | None = Field(default=None, max_length=512)
    notes: str | None = Field(default=None, max_length=2000)


class CancelProductionJobRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class HoldProductionJobRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ArtworkDownloadSchema(BaseModel):
    """Where the operator's browser can fetch this job's print file."""

    download_url: str
    filename: str
    sha256: str
    content_type: str
    expires_in_seconds: int
    width_px: PositiveInt
    height_px: PositiveInt
    embedded_dpi: PositiveInt


class PackingSlipAddress(BaseModel):
    name: str | None = None
    street: str | None = None
    city: str | None = None
    province: str | None = None
    postal_code: str | None = None
    country: str | None = None
    phone: str | None = None


class PackingSlipLine(BaseModel):
    product_name: str
    quantity: int
    unit_price: float | None = None
    currency: str


class PackingSlipSchema(BaseModel):
    """Structured packing slip; the admin UI renders and prints it."""

    job_id: UUID
    order_id: UUID
    order_placed_at: datetime
    issued_at: datetime
    customer_email: str
    merchant_name: str
    support_email: str
    ship_to: PackingSlipAddress
    line: PackingSlipLine
    print_specification: PrintSpecification | None = None
    notes: str | None = None
