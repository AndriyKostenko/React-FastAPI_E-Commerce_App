from uuid import UUID, uuid4
from datetime import datetime, timezone

from pydantic import BaseModel, EmailStr, PositiveFloat, Field

from contracts.order import ConfirmedOrderAddress, ConfirmedOrderItem, OrderItem
from contracts.services_enums import Services
from contracts.event_enums import OrderEvents, UserEvents
from contracts.limits import Code, LINES_MAX, MONEY_MAX, Money, Name


class BaseEvent(BaseModel):
    """Base class for all events"""
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service: Code
    event_type: Code
    schema_version: int = Field(default=1, ge=1, le=1000)
    correlation_id: UUID = Field(default_factory=uuid4)


# ============== USER SAGA EVENTS ==============
class UserBaseEvent(BaseEvent):
    service: Code = Field(default_factory=lambda: Services.USER_SERVICE)
    user_email: EmailStr
    user_id: UUID | None = None


class UserDeletedEvent(UserBaseEvent):
    """Event published when a user account is deleted"""
    event_type: Code = Field(default_factory=lambda: UserEvents.USER_DELETED)


# ============== ORDER SAGA EVENTS ==============
class OrderBaseEvent(BaseEvent):
    order_id: UUID
    user_id: UUID
    user_email: EmailStr
    service: Code = Field(default_factory=lambda: Services.ORDER_SERVICE)


class OrderCreatedEvent(OrderBaseEvent):
    """Event published when an order is created (start of SAGA)"""
    items: list[OrderItem] = Field(max_length=LINES_MAX)
    total_amount: PositiveFloat = Field(le=float(MONEY_MAX))
    event_type: Code = Field(default_factory=lambda: OrderEvents.ORDER_CREATED)


class OrderConfirmedEvent(OrderBaseEvent):
    """Event published when order is confirmed (SAGA success)."""
    event_type: Code = Field(default_factory=lambda: OrderEvents.ORDER_CONFIRMED)
    items: list[ConfirmedOrderItem] = Field(default_factory=list, max_length=LINES_MAX)
    address: ConfirmedOrderAddress | None = None
    # The CJ logistics option the customer paid for and CJ's quoted USD price.
    shipping_logistic_name: Name | None = None
    shipping_cost_usd: Money | None = None
