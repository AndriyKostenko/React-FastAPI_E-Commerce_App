from decimal import Decimal
from uuid import UUID, uuid4
from datetime import datetime, timezone

from pydantic import BaseModel, EmailStr, PositiveFloat, Field

from contracts.order import ConfirmedOrderAddress, ConfirmedOrderItem, OrderItem
from contracts.services_enums import Services
from contracts.event_enums import OrderEvents


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


class OrderCreatedEvent(OrderBaseEvent):
    """Event published when an order is created (start of SAGA)"""
    items: list[OrderItem]
    total_amount: PositiveFloat
    event_type: str = Field(default_factory=lambda: OrderEvents.ORDER_CREATED)


class OrderConfirmedEvent(OrderBaseEvent):
    """Event published when order is confirmed (SAGA success)."""
    event_type: str = Field(default_factory=lambda: OrderEvents.ORDER_CONFIRMED)
    items: list[ConfirmedOrderItem] = Field(default_factory=list)
    address: ConfirmedOrderAddress | None = None
    # The CJ logistics option the customer paid for and CJ's quoted USD price.
    shipping_logistic_name: str | None = None
    shipping_cost_usd: Decimal | None = None
