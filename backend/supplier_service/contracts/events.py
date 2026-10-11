from decimal import Decimal
from uuid import UUID, uuid4
from datetime import datetime, timezone

from pydantic import BaseModel, EmailStr, Field, model_validator

from contracts.order import ConfirmedOrderAddress, ConfirmedOrderItem, OrderItem
from contracts.supplier import GenericSupplierProduct, SupplierStockLevel
from contracts.services_enums import Services
from contracts.event_enums import InventoryEvents, OrderEvents, SupplierEvents


class BaseEvent(BaseModel):
    """Base class for all events"""
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service: str
    event_type: str
    schema_version: int = 1
    correlation_id: UUID = Field(default_factory=uuid4)


# ============== ORDER SAGA EVENTS ==============
class OrderBaseEvent(BaseEvent):
    order_id: UUID
    user_id: UUID
    user_email: EmailStr
    service: str = Field(default_factory=lambda: Services.ORDER_SERVICE)


class OrderConfirmedEvent(OrderBaseEvent):
    """Event published when order is confirmed (SAGA success)."""
    event_type: str = Field(default_factory=lambda: OrderEvents.ORDER_CONFIRMED)
    items: list[ConfirmedOrderItem] = Field(default_factory=list)
    address: ConfirmedOrderAddress | None = None
    # The CJ logistics option the customer paid for and CJ's quoted USD price.
    shipping_logistic_name: str | None = None
    shipping_cost_usd: Decimal | None = None


class OrderCancelledEvent(OrderBaseEvent):
    """Event published when order is cancelled (SAGA compensation).

    ``reconciliation_required`` is set when the order was cancelled after
    goods had already been made or posted — a printed garment, a parcel in the
    post. Refunding such an order automatically pays back money for stock that
    is already spent or gone, so payment_service holds the refund for a human
    return decision instead.
    """
    event_type: str = Field(default_factory=lambda: OrderEvents.ORDER_CANCELLED)
    reason: str
    reconciliation_required: bool = False


class CJOrderPaidEvent(OrderBaseEvent):
    """CJ confirmed the order and was paid from our CJ balance."""
    event_type: str = Field(default_factory=lambda: OrderEvents.CJ_ORDER_PAID)
    service: str = "supplier-service"
    cj_order_number: str
    amount_usd: Decimal | None = None


class CJOrderFailedEvent(OrderBaseEvent):
    """Definitive pre-creation CJ failure requiring central Saga compensation."""
    event_type: str = Field(default_factory=lambda: OrderEvents.CJ_ORDER_FAILED)
    reason: str


class InventoryReleaseRequested(OrderBaseEvent):
    """Event published when inventory needs to be released (compensation)"""
    event_type: str = Field(default_factory=lambda: InventoryEvents.INVENTORY_RELEASE_REQUESTED)
    items: list[OrderItem]
    reason: str


# ============== SHIPPING SAGA EVENTS ==============
class CJOrderCreatedEvent(OrderBaseEvent):
    """Event published when a CJ Dropshipping order has been created."""
    event_type: str = Field(default_factory=lambda: OrderEvents.CJ_ORDER_CREATED)
    cj_order_number: str


class OrderShippedBaseEvent(OrderBaseEvent):
    """Shared shape of every "the parcel is on its way" event.

    ``tracking_number`` is required: such an event exists to give the customer
    a parcel to follow, and neither CJ nor the in-house queue announces a
    dispatch before a tracking number exists.
    """
    tracking_number: str
    carrier: str | None = None
    tracking_url: str | None = None
    shipped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrderDeliveredBaseEvent(OrderBaseEvent):
    """Shared shape of every "the parcel arrived" event."""
    tracking_number: str | None = None
    delivered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CJOrderShippedEvent(OrderShippedBaseEvent):
    """Event published when CJ hands a dropshipped order to the carrier."""
    event_type: str = Field(default_factory=lambda: OrderEvents.CJ_ORDER_SHIPPED)
    cj_order_number: str
    logistic_name: str | None = None

    @model_validator(mode="after")
    def _carrier_defaults_to_logistic_name(self) -> "CJOrderShippedEvent":
        """CJ names the carrier ``logisticName``; expose it as ``carrier`` too."""
        if self.carrier is None and self.logistic_name:
            self.carrier = self.logistic_name
        return self


class CJOrderDeliveredEvent(OrderDeliveredBaseEvent):
    """Event published when CJ reports a dropshipped order as delivered."""
    event_type: str = Field(default_factory=lambda: OrderEvents.CJ_ORDER_DELIVERED)
    cj_order_number: str


# ============== SUPPLIER EVENTS ==============
class SupplierBaseEvent(BaseEvent):
    """Base class for supplier-related events."""
    service: str = Field(default_factory=lambda: Services.SUPPLIER_SERVICE)
    supplier_id: str


class SupplierStockUpdatedEvent(SupplierBaseEvent):
    """
    Current sellable stock for a batch of the supplier products we sell.

    ``measured_at`` is when the supplier was asked: a level older than the one
    a product already carries (a redelivered or retried message) is ignored,
    so stock never moves backwards in time.
    """
    event_type: str = Field(default_factory=lambda: SupplierEvents.SUPPLIER_STOCK_UPDATED)
    measured_at: datetime
    levels: list[SupplierStockLevel]


class SupplierProductsFetchedEvent(SupplierBaseEvent):
    """Event published when supplier_service fetches products from a supplier."""
    event_type: str = Field(default_factory=lambda: SupplierEvents.SUPPLIER_PRODUCTS_FETCHED)
    fetch_id: UUID
    batch_id: UUID = Field(default_factory=uuid4)
    batch_number: int = Field(ge=1)
    total_batches: int = Field(ge=1)
    products: list["GenericSupplierProduct"]


class SupplierProductImportCompletedEvent(BaseEvent):
    """Event published after a batch commits, including any item rejections."""
    service: str = Field(default_factory=lambda: Services.PRODUCT_SERVICE)
    event_type: str = Field(default_factory=lambda: SupplierEvents.SUPPLIER_PRODUCT_IMPORT_COMPLETED)
    supplier_id: str
    fetch_id: UUID
    batch_id: UUID
    batch_number: int = Field(ge=1)
    total_batches: int = Field(ge=1)
    imported: int
    updated: int
    failed: int
    errors: list[str] = Field(default_factory=list)


class SupplierProductImportFailedEvent(BaseEvent):
    """Event published by product_service when supplier product import failed."""
    service: str = Field(default_factory=lambda: Services.PRODUCT_SERVICE)
    event_type: str = Field(default_factory=lambda: SupplierEvents.SUPPLIER_PRODUCT_IMPORT_FAILED)
    supplier_id: str
    fetch_id: UUID
    batch_id: UUID
    batch_number: int = Field(ge=1)
    total_batches: int = Field(ge=1)
    reason: str
