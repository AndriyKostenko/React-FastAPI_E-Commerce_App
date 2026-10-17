from decimal import Decimal
from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, EmailStr, PositiveFloat, PositiveInt, Field, model_validator

from contracts.order import ConfirmedOrderAddress, ConfirmedOrderItem, OrderItem
from contracts.returns import ReturnFault, ReturnLineSummary, ReturnReason
from contracts.services_enums import Services
from contracts.event_enums import OrderEvents, PaymentEvents, ProductionEvents, UserEvents


class BaseEvent(BaseModel):
    """Base class for all events"""
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service: str
    event_type: str
    schema_version: int = 1
    correlation_id: UUID = Field(default_factory=uuid4)


# ============== USER SAGA EVENTS ==============
class UserBaseEvent(BaseEvent):
    service: str = Field(default_factory=lambda: Services.USER_SERVICE)
    user_email: EmailStr
    user_id: UUID | None = None


class UserRegisteredEvent(UserBaseEvent):
    """Event published when a user registers"""
    event_type: str = Field(default_factory=lambda: UserEvents.USER_REGISTERED)
    token: str


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


class ExistingAccountRegistrationEvent(UserBaseEvent):
    """Event published when someone registers with the email of a verified account.

    The sign-up form answers the same either way (it must not reveal who has
    an account), so the owner is told by email instead.
    """
    event_type: str = Field(default_factory=lambda: UserEvents.USER_REGISTRATION_EXISTING)


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


# ============== PAYMENT SAGA EVENTS ==============
class PaymentBaseEvent(BaseEvent):
    order_id: UUID
    user_id: UUID
    user_email: EmailStr
    service: str = Field(default_factory=lambda: Services.PAYMENT_SERVICE)
    payment_intent_id: str
    amount: float
    currency: str


class PaymentSucceededEvent(PaymentBaseEvent):
    """The authorized amount was captured: the customer is charged."""
    event_type: str = Field(default_factory=lambda: PaymentEvents.PAYMENT_SUCCEEDED)


class PaymentFailedEvent(PaymentBaseEvent):
    """Event published when a Stripe payment intent fails"""
    event_type: str = Field(default_factory=lambda: PaymentEvents.PAYMENT_FAILED)
    reason: str


class RefundScope(StrEnum):
    """How much of what was charged a refund leaves behind: the customer is told accordingly."""

    PART = "part"    # money is still captured after this refund
    REST = "rest"    # the last of it, after earlier refunds
    WHOLE = "whole"  # all of it, in this one refund

    @classmethod
    def after(cls, *, refunded_total_cents: int, this_refund_cents: int, left_cents: int) -> "RefundScope":
        """``refunded_total_cents`` counts every refund so far, this one included."""
        if left_cents > 0:
            return cls.PART
        return cls.WHOLE if refunded_total_cents == this_refund_cents else cls.REST


class PaymentRefundedEvent(PaymentBaseEvent):
    """
    Money went back to the customer: the whole payment after a cancellation,
    or part of it for a refund order_service requested (``refund_id`` set).
    """
    event_type: str = Field(default_factory=lambda: PaymentEvents.PAYMENT_REFUNDED)
    refund_id: UUID | None = None
    refunded_amount_cents: int | None = None
    # True when the card had not been captured yet: the customer is simply
    # charged that much less, rather than refunded.
    applied_before_capture: bool = False
    # None on events published before the scope existed.
    refund_scope: RefundScope | None = None


class PaymentCancelledEvent(PaymentBaseEvent):
    """Event published when a Stripe payment intent is cancelled"""
    event_type: str = Field(default_factory=lambda: PaymentEvents.PAYMENT_CANCELLED)
    reason: str


class PaymentDisputeEvent(PaymentBaseEvent):
    """
    The customer's bank opened or settled a dispute (chargeback) on the charge.
    Nothing is done automatically: the order is flagged and an admin told.
    """
    event_type: str = Field(default_factory=lambda: PaymentEvents.PAYMENT_DISPUTE_OPENED)
    dispute_id: str
    disputed_amount_cents: int
    reason: str
    # needs_response / under_review / won / lost / warning_closed ...
    dispute_status: str
    evidence_due_by: datetime | None = None


class OrderReturnEvent(OrderBaseEvent):
    """
    A customer return was requested, approved or rejected.

    One shape for all three: the admin is alerted about a request, the
    customer is told the decision. ``return_address`` is only set on an
    approval where goods have to come back.
    """
    event_type: str = Field(default_factory=lambda: OrderEvents.RETURN_REQUESTED)
    return_id: UUID
    reason: ReturnReason
    fault: ReturnFault
    description: str
    lines: list[ReturnLineSummary]
    photo_count: int = 0
    admin_note: str | None = None
    return_address: str | None = None

    @property
    def ships_back(self) -> bool:
        return any(line.ships_back for line in self.lines)


# ============== SHIPPING SAGA EVENTS ==============
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


# ============== IN-HOUSE PRODUCTION EVENTS ==============
class ProductionJobBaseEvent(OrderBaseEvent):
    """One in-house print job moving through the operator's work queue.

    A production job covers exactly one custom order line, so these events
    carry ``order_item_id`` as well as ``order_id``: a mixed cart can hold a
    custom line alongside a CJ or catalog line that ships on its own schedule.
    """
    job_id: UUID
    order_item_id: UUID
    quantity: PositiveInt = 1
    product_name: str | None = None


class ProductionJobShippedEvent(ProductionJobBaseEvent, OrderShippedBaseEvent):
    """Event published when the operator posts the finished garment."""
    event_type: str = Field(default_factory=lambda: ProductionEvents.PRODUCTION_JOB_SHIPPED)


class ProductionJobDeliveredEvent(ProductionJobBaseEvent, OrderDeliveredBaseEvent):
    """Event published when an in-house parcel is confirmed as delivered."""
    event_type: str = Field(default_factory=lambda: ProductionEvents.PRODUCTION_JOB_DELIVERED)


class ProductionJobCancelledEvent(ProductionJobBaseEvent):
    """
    Event published when a job leaves the queue without being fulfilled.

    ``refunded_amount`` is what went back to the customer automatically (None
    when nothing did: the garment was already made, or a human decides), and
    ``shipping_refunded`` says whether it included the order's shipping, which
    happens once no line of the order is left to ship.
    """
    event_type: str = Field(default_factory=lambda: ProductionEvents.PRODUCTION_JOB_CANCELLED)
    reason: str
    reconciliation_required: bool = False
    refunded_amount: Decimal | None = None
    shipping_refunded: bool = False
