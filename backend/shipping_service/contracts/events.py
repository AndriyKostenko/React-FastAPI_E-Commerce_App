from uuid import UUID, uuid4
from datetime import datetime, timezone

from pydantic import BaseModel, EmailStr, Field

from contracts.order import ConfirmedOrderAddress, ConfirmedOrderItem
from contracts.services_enums import Services
from contracts.event_enums import OrderEvents, ShippingEvents
from contracts.limits import ClippedText, Code, Identifier, LINES_MAX, Money, Name


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


class OrderConfirmedEvent(OrderBaseEvent):
    """Event published when order is confirmed (SAGA success)."""
    event_type: Code = Field(default_factory=lambda: OrderEvents.ORDER_CONFIRMED)
    items: list[ConfirmedOrderItem] = Field(default_factory=list, max_length=LINES_MAX)
    address: ConfirmedOrderAddress | None = None
    # The CJ logistics option the customer paid for and CJ's quoted USD price.
    shipping_logistic_name: Name | None = None
    shipping_cost_usd: Money | None = None


class OrderCancelledEvent(OrderBaseEvent):
    """Event published when order is cancelled (SAGA compensation).

    ``reconciliation_required`` is set when the order was cancelled after
    goods had already been made or posted — a printed garment, a parcel in the
    post. Refunding such an order automatically pays back money for stock that
    is already spent or gone, so payment_service holds the refund for a human
    return decision instead.
    """
    event_type: Code = Field(default_factory=lambda: OrderEvents.ORDER_CANCELLED)
    reason: ClippedText
    reconciliation_required: bool = False


# ============== SHIPPING SAGA EVENTS ==============
class ShipmentBaseEvent(BaseEvent):
    shipment_id: UUID
    order_id: UUID
    user_id: UUID
    user_email: EmailStr
    service: Code = Field(default_factory=lambda: Services.SHIPPING_SERVICE)


class ShipmentCreatedEvent(ShipmentBaseEvent):
    """Event published when a shipment is created for an order"""
    event_type: Code = Field(default_factory=lambda: ShippingEvents.SHIPMENT_CREATED)
    method_id: UUID
    estimated_delivery: Code


class ShipmentShippedEvent(ShipmentBaseEvent):
    """Event published when a shipment is handed to the carrier"""
    event_type: Code = Field(default_factory=lambda: ShippingEvents.SHIPMENT_SHIPPED)
    tracking_number: Identifier
    shipped_at: Code


class ShipmentDeliveredEvent(ShipmentBaseEvent):
    """Event published when a shipment is delivered"""
    event_type: Code = Field(default_factory=lambda: ShippingEvents.SHIPMENT_DELIVERED)
    delivered_at: Code


class ShipmentCancelledEvent(ShipmentBaseEvent):
    """Event published when a shipment is cancelled"""
    event_type: Code = Field(default_factory=lambda: ShippingEvents.SHIPMENT_CANCELLED)
    reason: ClippedText
