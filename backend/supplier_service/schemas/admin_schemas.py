"""What the back office sees of supplier-service's tables (see shared.admin.admin_tables)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CJOrderAdminSchema(BaseModel):
    """One CJ order we placed (an attempt row); the request payload is left out."""
    id: UUID
    order_id: UUID
    user_id: UUID
    user_email: str | None
    status: str
    cj_order_number: str | None
    cj_order_status: str | None
    tracking_number: str | None
    logistic_name: str | None
    cj_order_amount_usd: Decimal | None
    expected_max_amount_usd: Decimal | None
    payment_attempts: int
    is_sandbox: bool
    last_error: str | None
    paid_at: datetime | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    cancelled_at: datetime | None
    last_polled_at: datetime | None
    date_created: datetime
    date_updated: datetime | None


class SupplierSyncAdminSchema(BaseModel):
    id: UUID
    supplier_id: str
    status: str
    products_fetched: int
    products_emitted: int
    products_imported: int
    products_updated: int
    products_failed: int
    processed_batches: int
    total_batches: int
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
    date_created: datetime


class SupplierConfigAdminSchema(BaseModel):
    id: UUID
    supplier_id: str
    name: str
    provider_type: str
    is_active: bool
    sync_interval_minutes: int
    default_category_name: str | None
    date_created: datetime
    date_updated: datetime | None


class SupplierConfigAdminUpdate(BaseModel):
    """What an admin may change: whether and how often the catalogue syncs."""
    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None
    sync_interval_minutes: int | None = Field(default=None, ge=15, le=7 * 24 * 60)
    default_category_name: str | None = Field(default=None, min_length=1, max_length=100)

    model_config = ConfigDict(extra="forbid")
