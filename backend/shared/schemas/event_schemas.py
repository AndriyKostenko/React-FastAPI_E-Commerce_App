from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, EmailStr, PositiveFloat

from schemas.order_schemas import OrderItemBase


class BaseEvent(BaseModel):
    """Base class for all events"""
    event_id: UUID
    timestamp: datetime
    service: str
    event_type: str

# ============== USER SAGA EVENTS ==============

class UserRegisteredEvent(BaseEvent):
    """Event published when a user registers"""
    email: EmailStr
    token: str

class UserLoginEvent(BaseEvent):
    """Event published when a user logs in"""
    email: EmailStr

class PasswordResetRequestedEvent(BaseEvent):
    """Event published when password reset is requested"""
    email: EmailStr
    reset_token: str

class PasswordResetSuccessEvent(BaseEvent):
    """Event published when pussword reset success"""
    email: EmailStr

class EmailVerificationRequestedEvent(BaseEvent):
    """Event published when email verification is requested"""
    email: EmailStr
    verification_token: str | None = None
    event_type: str


# ============== ORDER SAGA EVENTS ==============

class OrderCreatedEvent(BaseEvent):
    """Event published when an order is created (start of SAGA)"""
    order_id: UUID
    user_id: UUID
    items: list[OrderItemBase]
    total_amount: PositiveFloat


class OrderConfirmedEvent(BaseEvent):
    """Event published when order is confirmed (SAGA success)"""
    order_id: UUID
    user_id: UUID


class OrderCancelledEvent(BaseEvent):
    """Event published when order is cancelled (SAGA compensation)"""
    order_id: UUID
    user_id: UUID
    reason: str


class InventoryReserveRequested(BaseEvent):
    """Event published when inventory reserve is requested"""
    order_id: UUID
    user_id: UUID
    items: list[OrderItemBase]


class InventoryReleaseRequested(BaseEvent):
    """Event published when inventory needs to be released (compensation)"""
    order_id: UUID
    user_id: UUID
    items: list[OrderItemBase]
    reason: str

# ============== PRODUCT SAGA EVENTS ==============
class InventoryReserveSucceeded(BaseEvent):
    """Event published when inventory reserve succeeds"""
    order_id: UUID
    user_id: UUID
    reserved_items: list[OrderItemBase]


class InventoryReserveFailed(BaseEvent):
    """Event published when inventory reserve fails"""
    order_id: UUID
    user_id: UUID
    reasons: str
    failed_items: list[OrderItemBase]
