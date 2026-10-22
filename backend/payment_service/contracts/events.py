from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field

from contracts.services_enums import Services
from contracts.event_enums import OrderEvents, PaymentCommands, PaymentEvents
from contracts.limits import CENTS_MAX, Cents, ClippedText, Code, Identifier


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


# ============== PAYMENT SAGA EVENTS ==============
class PaymentBaseEvent(BaseEvent):
    order_id: UUID
    user_id: UUID
    user_email: EmailStr
    service: Code = Field(default_factory=lambda: Services.PAYMENT_SERVICE)
    payment_intent_id: Identifier
    # In cents, as Stripe counts it.
    amount: float = Field(ge=0, le=CENTS_MAX)
    currency: Code


class PaymentAuthorizedEvent(PaymentBaseEvent):
    """The card is authorized for the order total; nothing is charged yet."""
    event_type: Code = Field(default_factory=lambda: PaymentEvents.PAYMENT_AUTHORIZED)


class PaymentSucceededEvent(PaymentBaseEvent):
    """The authorized amount was captured: the customer is charged."""
    event_type: Code = Field(default_factory=lambda: PaymentEvents.PAYMENT_SUCCEEDED)


class PaymentFailedEvent(PaymentBaseEvent):
    """Event published when a Stripe payment intent fails"""
    event_type: Code = Field(default_factory=lambda: PaymentEvents.PAYMENT_FAILED)
    reason: ClippedText


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
    event_type: Code = Field(default_factory=lambda: PaymentEvents.PAYMENT_REFUNDED)
    refund_id: UUID | None = None
    refunded_amount_cents: Cents | None = None
    # True when the card had not been captured yet: the customer is simply
    # charged that much less, rather than refunded.
    applied_before_capture: bool = False
    # None on events published before the scope existed.
    refund_scope: RefundScope | None = None


class PaymentRefundFailedEvent(PaymentBaseEvent):
    """A refund order_service requested could not be made."""
    event_type: Code = Field(default_factory=lambda: PaymentEvents.PAYMENT_REFUND_FAILED)
    refund_id: UUID
    reason: ClippedText


class PaymentCancelledEvent(PaymentBaseEvent):
    """Event published when a Stripe payment intent is cancelled"""
    event_type: Code = Field(default_factory=lambda: PaymentEvents.PAYMENT_CANCELLED)
    reason: ClippedText


class PaymentDisputeEvent(PaymentBaseEvent):
    """
    The customer's bank opened or settled a dispute (chargeback) on the charge.
    Nothing is done automatically: the order is flagged and an admin told.
    """
    event_type: Code = Field(default_factory=lambda: PaymentEvents.PAYMENT_DISPUTE_OPENED)
    dispute_id: Identifier
    disputed_amount_cents: Cents
    reason: ClippedText
    # needs_response / under_review / won / lost / warning_closed ...
    dispute_status: Code
    evidence_due_by: datetime | None = None


class PaymentCommandBase(BaseEvent):
    """An order_service instruction about the card held for one order."""
    order_id: UUID
    user_id: UUID
    user_email: EmailStr
    service: Code = Field(default_factory=lambda: Services.ORDER_SERVICE)


class PaymentCaptureRequested(PaymentCommandBase):
    """Fulfillment is secured: charge the authorized card."""
    event_type: Code = Field(default_factory=lambda: PaymentCommands.CAPTURE_REQUESTED)


class PaymentRefundRequested(PaymentCommandBase):
    """Give back part of an order's payment: chosen lines, maybe shipping."""
    event_type: Code = Field(default_factory=lambda: PaymentCommands.REFUND_REQUESTED)
    refund_id: UUID
    amount_cents: int = Field(gt=0, le=CENTS_MAX)
    reason: ClippedText


class PaymentReleaseRequested(PaymentCommandBase):
    """Money is held for an order that cannot be fulfilled: void or refund it.

    Sent when a payment lands for an order that is unknown or already
    cancelled, so a card hold can never outlive the order it was for.
    """
    event_type: Code = Field(default_factory=lambda: PaymentCommands.RELEASE_REQUESTED)
    payment_intent_id: Identifier | None = None
    reason: ClippedText
