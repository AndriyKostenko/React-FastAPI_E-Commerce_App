from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, EmailStr, PositiveFloat, Field, model_validator

from contracts.order import ConfirmedOrderAddress, ConfirmedOrderItem, OrderItem
from contracts.returns import RefundedLineSummary, ReturnFault, ReturnLineSummary, ReturnReason
from contracts.services_enums import Services
from contracts.event_enums import (
    ArtworkEvents,
    InventoryEvents,
    OrderEvents,
    PaymentCommands,
    PaymentEvents,
    ProductionEvents,
    ShippingEvents,
)
from contracts.limits import (
    CENTS_MAX, Cents, ClippedText, Code, Count, Identifier, LINES_MAX, MONEY_MAX, Money, Name, PositiveCount, Url,
)


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


class CJOrderPaidEvent(OrderBaseEvent):
    """CJ confirmed the order and was paid from our CJ balance."""
    event_type: Code = Field(default_factory=lambda: OrderEvents.CJ_ORDER_PAID)
    service: Code = "supplier-service"
    cj_order_number: Identifier
    amount_usd: Money | None = None


class CJOrderFailedEvent(OrderBaseEvent):
    """Definitive pre-creation CJ failure requiring central Saga compensation."""
    event_type: Code = Field(default_factory=lambda: OrderEvents.CJ_ORDER_FAILED)
    reason: ClippedText


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


class OrderReturnEvent(OrderBaseEvent):
    """
    A customer return was requested, approved or rejected.

    One shape for all three: the admin is alerted about a request, the
    customer is told the decision. ``return_address`` is only set on an
    approval where goods have to come back.
    """
    event_type: Code = Field(default_factory=lambda: OrderEvents.RETURN_REQUESTED)
    return_id: UUID
    reason: ReturnReason
    fault: ReturnFault
    description: ClippedText
    lines: list[ReturnLineSummary] = Field(max_length=LINES_MAX)
    photo_count: Count = 0
    admin_note: ClippedText | None = None
    return_address: ClippedText | None = None

    @property
    def ships_back(self) -> bool:
        return any(line.ships_back for line in self.lines)


class OrderReturnRefundedEvent(OrderBaseEvent):
    """
    The refund for a customer return went through: payment-service confirmed
    it to order-service, which tells the customer (notification-service
    emails it). One event per refund; a return refunded in two steps
    (returnless lines on approval, the rest on receipt) sends two.
    """
    event_type: Code = Field(default_factory=lambda: OrderEvents.RETURN_REFUNDED)
    return_id: UUID
    refund_id: UUID
    # What went back: the lines, the shipping when included, and their tax (CAD).
    amount: Money
    includes_shipping: bool
    lines: list[RefundedLineSummary] = Field(max_length=LINES_MAX)


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


class CJOrderCreatedEvent(OrderBaseEvent):
    """Event published when a CJ Dropshipping order has been created."""
    event_type: Code = Field(default_factory=lambda: OrderEvents.CJ_ORDER_CREATED)
    cj_order_number: Identifier


class OrderShippedBaseEvent(OrderBaseEvent):
    """Shared shape of every "the parcel is on its way" event.

    ``tracking_number`` is required: such an event exists to give the customer
    a parcel to follow, and neither CJ nor the in-house queue announces a
    dispatch before a tracking number exists.
    """
    tracking_number: Identifier
    carrier: Name | None = None
    tracking_url: Url | None = None
    shipped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrderDeliveredBaseEvent(OrderBaseEvent):
    """Shared shape of every "the parcel arrived" event."""
    tracking_number: Identifier | None = None
    delivered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CJOrderShippedEvent(OrderShippedBaseEvent):
    """Event published when CJ hands a dropshipped order to the carrier."""
    event_type: Code = Field(default_factory=lambda: OrderEvents.CJ_ORDER_SHIPPED)
    cj_order_number: Identifier
    logistic_name: Name | None = None

    @model_validator(mode="after")
    def _carrier_defaults_to_logistic_name(self) -> "CJOrderShippedEvent":
        """CJ names the carrier ``logisticName``; expose it as ``carrier`` too."""
        if self.carrier is None and self.logistic_name:
            self.carrier = self.logistic_name
        return self


class CJOrderDeliveredEvent(OrderDeliveredBaseEvent):
    """Event published when CJ reports a dropshipped order as delivered."""
    event_type: Code = Field(default_factory=lambda: OrderEvents.CJ_ORDER_DELIVERED)
    cj_order_number: Identifier


# ============== IN-HOUSE PRODUCTION EVENTS ==============
class ProductionJobBaseEvent(OrderBaseEvent):
    """One in-house print job moving through the operator's work queue.

    A production job covers exactly one custom order line, so these events
    carry ``order_item_id`` as well as ``order_id``: a mixed cart can hold a
    custom line alongside a CJ or catalog line that ships on its own schedule.
    """
    job_id: UUID
    order_item_id: UUID
    quantity: PositiveCount = 1
    product_name: Name | None = None


class ProductionJobStartedEvent(ProductionJobBaseEvent):
    """Event published when the operator picks a queued job up for printing."""
    event_type: Code = Field(default_factory=lambda: ProductionEvents.PRODUCTION_JOB_STARTED)


class ProductionJobPrintedEvent(ProductionJobBaseEvent):
    """Event published when the garment has been printed and is awaiting post."""
    event_type: Code = Field(default_factory=lambda: ProductionEvents.PRODUCTION_JOB_PRINTED)


class ProductionJobShippedEvent(ProductionJobBaseEvent, OrderShippedBaseEvent):
    """Event published when the operator posts the finished garment."""
    event_type: Code = Field(default_factory=lambda: ProductionEvents.PRODUCTION_JOB_SHIPPED)


class ProductionJobDeliveredEvent(ProductionJobBaseEvent, OrderDeliveredBaseEvent):
    """Event published when an in-house parcel is confirmed as delivered."""
    event_type: Code = Field(default_factory=lambda: ProductionEvents.PRODUCTION_JOB_DELIVERED)


class ProductionJobCancelledEvent(ProductionJobBaseEvent):
    """
    Event published when a job leaves the queue without being fulfilled.

    ``refunded_amount`` is what went back to the customer automatically (None
    when nothing did: the garment was already made, or a human decides), and
    ``shipping_refunded`` says whether it included the order's shipping, which
    happens once no line of the order is left to ship.
    """
    event_type: Code = Field(default_factory=lambda: ProductionEvents.PRODUCTION_JOB_CANCELLED)
    reason: ClippedText
    reconciliation_required: bool = False
    refunded_amount: Money | None = None
    shipping_refunded: bool = False


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
