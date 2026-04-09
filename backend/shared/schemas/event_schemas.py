from uuid import UUID, uuid4
from datetime import datetime, timezone

from pydantic import BaseModel, EmailStr, PositiveFloat, Field

from shared.schemas.order_schemas import OrderItemBase
from shared.enums.services_enums import Services
from shared.enums.event_enums import UserEvents, OrderEvents, InventoryEvents

class BaseEvent(BaseModel):
    """Base class for all events"""
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service: str
    event_type: str

# ============== USER SAGA EVENTS ==============
class UserBaseEvent(BaseEvent):
    service: str = Field(default_factory=lambda: Services.USER_SERVICE)
    user_email: EmailStr

class UserRegisteredEvent(UserBaseEvent):
    """Event published when a user registers"""
    event_type: str = Field(default_factory=lambda: UserEvents.USER_REGISTERED)
    token: str

class UserRegistrationFailedEvent(UserBaseEvent):
    """Event published when a user registration failed"""
    event_type: str = Field(default_factory=lambda: UserEvents.USER_REGISTRATION_FAILED)


class UserLoginEvent(UserBaseEvent):
    """Event published when a user logs in"""
    event_type: str = Field(default_factory=lambda: UserEvents.USER_LOGGED_IN)

class PasswordResetRequestedEvent(UserBaseEvent):
    """Event published when password reset is requested"""
    event_type: str = Field(default_factory=lambda: UserEvents.USER_PASSWORD_RESET_REQUEST)
    reset_token: str

class PasswordResetSuccessEvent(UserBaseEvent):
    """Event published when pussword reset success"""
    event_type: str = Field(default_factory=lambda: UserEvents.USER_PASSWORD_RESET_SUCCESS)

class EmailVerificationRequestedEvent(UserBaseEvent):
    """Event published when email verification is requested"""
    event_type: str = Field(default_factory=lambda: UserEvents.USER_EMAIL_VERIFICATION_REQUEST)
    verification_token: str | None = None

class EmailVerificationEvent(UserBaseEvent):
    """Event published when email verification is proceeded"""
    event_type: str = Field(default_factory=lambda: UserEvents.USER_EMAIL_VERIFIED)


# ============== ORDER SAGA EVENTS ==============
class OrderBaseEvent(BaseEvent):
    order_id: UUID
    user_id: UUID
    user_email: EmailStr
    service: str = Field(default_factory=lambda: Services.ORDER_SERVICE)

class OrderCreatedEvent(OrderBaseEvent):
    """Event published when an order is created (start of SAGA)"""
    items: list[OrderItemBase]
    total_amount: PositiveFloat
    event_type: str = Field(default_factory=lambda: OrderEvents.ORDER_CREATED)


class OrderConfirmedEvent(OrderBaseEvent):
    """Event published when order is confirmed (SAGA success)"""
    event_type: str = Field(default_factory=lambda: OrderEvents.ORDER_CONFIRMED)


class OrderCancelledEvent(OrderBaseEvent):
    """Event published when order is cancelled (SAGA compensation)"""
    event_type: str = Field(default_factory=lambda: OrderEvents.ORDER_CANCELLED)
    reason: str


class InventoryReserveRequested(OrderBaseEvent):
    """Event published when inventory reserve is requested"""
    event_type: str = Field(default_factory=lambda: InventoryEvents.INVENTORY_RESERVE_REQUESTED)
    items: list[OrderItemBase]


class InventoryReleaseRequested(OrderBaseEvent):
    """Event published when inventory needs to be released (compensation)"""
    event_type: str = Field(default_factory=lambda: InventoryEvents.INVENTORY_RELEASE_REQUESTED)
    items: list[OrderItemBase]
    reason: str

# ============== PRODUCT SAGA EVENTS ==============
class InventoryReserveSucceeded(OrderBaseEvent):
    """Event published when inventory reserve succeeds"""
    event_type: str = Field(default_factory=lambda: InventoryEvents.INVENTORY_RESERVE_SUCCEEDED)
    reserved_items: list[OrderItemBase]


class InventoryReserveFailed(OrderBaseEvent):
    """Event published when inventory reserve fails"""
    event_type: str = Field(default_factory=lambda: InventoryEvents.INVENTORY_RESERVE_FAILED)
    reasons: str
    failed_items: list[OrderItemBase]
