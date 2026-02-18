from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, EmailStr, PositiveFloat

from shared.schemas.order_schemas import OrderItemBase


class BaseEvent(BaseModel):
    """Base class for all events"""
    event_id: UUID
    timestamp: datetime
    service: str
    event_type: str

# ============== USER SAGA EVENTS ==============
class UserBaseEvent(BaseEvent):
    user_email: EmailStr

class UserRegisteredEvent(UserBaseEvent):
    """Event published when a user registers"""
    token: str

class UserRegistrationFailedEvent(UserBaseEvent):
    """Event published when a user registration failed"""
    ...


class UserLoginEvent(UserBaseEvent):
    """Event published when a user logs in"""
    ...

class PasswordResetRequestedEvent(UserBaseEvent):
    """Event published when password reset is requested"""
    reset_token: str

class PasswordResetSuccessEvent(UserBaseEvent):
    """Event published when pussword reset success"""
    ...

class EmailVerificationRequestedEvent(UserBaseEvent):
    """Event published when email verification is requested"""
    verification_token: str | None = None

class EmailVerificationEvent(UserBaseEvent):
    """Event published when email verification is proceeded"""
    ...

# ============== ORDER SAGA EVENTS ==============
class OrderBaseEvent(BaseEvent):
    order_id: UUID
    user_id: UUID
    user_email: EmailStr

class OrderCreatedEvent(OrderBaseEvent):
    """Event published when an order is created (start of SAGA)"""
    items: list[OrderItemBase]
    total_amount: PositiveFloat


class OrderConfirmedEvent(OrderBaseEvent):
    """Event published when order is confirmed (SAGA success)"""
    ...


class OrderCancelledEvent(OrderBaseEvent):
    """Event published when order is cancelled (SAGA compensation)"""
    reason: str


class InventoryReserveRequested(OrderBaseEvent):
    """Event published when inventory reserve is requested"""
    items: list[OrderItemBase]


class InventoryReleaseRequested(OrderBaseEvent):
    """Event published when inventory needs to be released (compensation)"""
    items: list[OrderItemBase]
    reason: str

# ============== PRODUCT SAGA EVENTS ==============
class InventoryReserveSucceeded(OrderBaseEvent):
    """Event published when inventory reserve succeeds"""
    reserved_items: list[OrderItemBase]


class InventoryReserveFailed(OrderBaseEvent):
    """Event published when inventory reserve fails"""
    reasons: str
    failed_items: list[OrderItemBase]
