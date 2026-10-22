from uuid import UUID, uuid4
from datetime import datetime, timezone

from pydantic import BaseModel, EmailStr, Field

from contracts.order import OrderItem
from contracts.supplier import GenericSupplierProduct, SupplierStockLevel
from contracts.services_enums import Services
from contracts.event_enums import ArtworkEvents, InventoryEvents, SupplierEvents
from contracts.limits import BATCH_MAX, COUNT_MAX, ClippedText, Code, Count, Identifier, LINES_MAX, Url


class BaseEvent(BaseModel):
    """Base class for all events"""
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service: Code
    event_type: Code
    schema_version: int = Field(default=1, ge=1, le=1000)
    correlation_id: UUID = Field(default_factory=uuid4)


# ============== ORDER SAGA EVENTS ==============
class OrderBaseEvent(BaseEvent):
    order_id: UUID
    user_id: UUID
    user_email: EmailStr
    service: Code = Field(default_factory=lambda: Services.ORDER_SERVICE)


class InventoryReserveRequested(OrderBaseEvent):
    """Event published when inventory reserve is requested"""
    event_type: Code = Field(default_factory=lambda: InventoryEvents.INVENTORY_RESERVE_REQUESTED)
    items: list[OrderItem] = Field(max_length=LINES_MAX)


class InventoryReleaseRequested(OrderBaseEvent):
    """Event published when inventory needs to be released (compensation)"""
    event_type: Code = Field(default_factory=lambda: InventoryEvents.INVENTORY_RELEASE_REQUESTED)
    items: list[OrderItem] = Field(max_length=LINES_MAX)
    reason: ClippedText


# ============== PRODUCT SAGA EVENTS ==============
class InventoryReserveSucceeded(OrderBaseEvent):
    """Event published when inventory reserve succeeds"""
    event_type: Code = Field(default_factory=lambda: InventoryEvents.INVENTORY_RESERVE_SUCCEEDED)
    reserved_items: list[OrderItem] = Field(max_length=LINES_MAX)


class InventoryReserveFailed(OrderBaseEvent):
    """Event published when inventory reserve fails"""
    event_type: Code = Field(default_factory=lambda: InventoryEvents.INVENTORY_RESERVE_FAILED)
    reasons: ClippedText
    failed_items: list[OrderItem] = Field(max_length=LINES_MAX)


# ============== ARTWORK RETENTION EVENTS ==============
class ArtworkRetentionBaseEvent(BaseEvent):
    """Links a paid order line to the stored print file it depends on.

    product_service owns the artwork object while order_service owns the
    reference to it. Without this link a cleanup job sweeping unreferenced
    generation drafts cannot tell a paid order's print file from an abandoned
    preview, so it could delete artwork that still has to be printed.
    """
    service: Code = Field(default_factory=lambda: Services.ORDER_SERVICE)
    order_id: UUID
    artwork_keys: list[Url] = Field(default_factory=list, max_length=LINES_MAX)


class ArtworkRetainedEvent(ArtworkRetentionBaseEvent):
    """Event published when an order is confirmed and its artwork must survive."""
    event_type: Code = Field(default_factory=lambda: ArtworkEvents.ARTWORK_RETAINED)


class ArtworkReleasedEvent(ArtworkRetentionBaseEvent):
    """Event published when an order is cancelled and its hold can be dropped."""
    event_type: Code = Field(default_factory=lambda: ArtworkEvents.ARTWORK_RELEASED)
    reason: ClippedText = ""


# ============== SUPPLIER EVENTS ==============
class SupplierBaseEvent(BaseEvent):
    """Base class for supplier-related events."""
    service: Code = Field(default_factory=lambda: Services.SUPPLIER_SERVICE)
    supplier_id: Identifier


class SupplierStockUpdatedEvent(SupplierBaseEvent):
    """
    Current sellable stock for a batch of the supplier products we sell.

    ``measured_at`` is when the supplier was asked: a level older than the one
    a product already carries (a redelivered or retried message) is ignored,
    so stock never moves backwards in time.
    """
    event_type: Code = Field(default_factory=lambda: SupplierEvents.SUPPLIER_STOCK_UPDATED)
    measured_at: datetime
    levels: list[SupplierStockLevel] = Field(max_length=BATCH_MAX)


class SupplierProductsFetchedEvent(SupplierBaseEvent):
    """Event published when supplier_service fetches products from a supplier."""
    event_type: Code = Field(default_factory=lambda: SupplierEvents.SUPPLIER_PRODUCTS_FETCHED)
    fetch_id: UUID
    batch_id: UUID = Field(default_factory=uuid4)
    batch_number: int = Field(ge=1, le=COUNT_MAX)
    total_batches: int = Field(ge=1, le=COUNT_MAX)
    products: list["GenericSupplierProduct"] = Field(max_length=BATCH_MAX)


class SupplierProductImportCompletedEvent(BaseEvent):
    """Event published after a batch commits, including any item rejections."""
    service: Code = Field(default_factory=lambda: Services.PRODUCT_SERVICE)
    event_type: Code = Field(default_factory=lambda: SupplierEvents.SUPPLIER_PRODUCT_IMPORT_COMPLETED)
    supplier_id: Identifier
    fetch_id: UUID
    batch_id: UUID
    batch_number: int = Field(ge=1, le=COUNT_MAX)
    total_batches: int = Field(ge=1, le=COUNT_MAX)
    imported: Count
    updated: Count
    failed: Count
    errors: list[ClippedText] = Field(default_factory=list, max_length=BATCH_MAX)


class SupplierProductImportFailedEvent(BaseEvent):
    """Event published by product_service when supplier product import failed."""
    service: Code = Field(default_factory=lambda: Services.PRODUCT_SERVICE)
    event_type: Code = Field(default_factory=lambda: SupplierEvents.SUPPLIER_PRODUCT_IMPORT_FAILED)
    supplier_id: Identifier
    fetch_id: UUID
    batch_id: UUID
    batch_number: int = Field(ge=1, le=COUNT_MAX)
    total_batches: int = Field(ge=1, le=COUNT_MAX)
    reason: ClippedText
