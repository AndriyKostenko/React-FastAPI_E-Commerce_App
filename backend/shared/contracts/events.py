from decimal import Decimal
from uuid import UUID, uuid4
from datetime import datetime, timezone

from pydantic import BaseModel, EmailStr, PositiveFloat, PositiveInt, Field, model_validator

from shared.contracts.order import ConfirmedOrderAddress, ConfirmedOrderItem, OrderItem
from shared.contracts.supplier import GenericSupplierProduct
from shared.enums.services_enums import Services
from shared.enums.event_enums import (
    ArtworkEvents,
    InventoryEvents,
    OrderEvents,
    PaymentCommands,
    PaymentEvents,
    ProductionEvents,
    ShippingEvents,
    SupplierEvents,
    UserEvents,
    WishlistEvents,
)

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


class UserDeletedEvent(UserBaseEvent):
    """Event published when a user account is deleted"""
    event_type: str = Field(default_factory=lambda: UserEvents.USER_DELETED)


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


class InventoryReserveRequested(OrderBaseEvent):
    """Event published when inventory reserve is requested"""
    event_type: str = Field(default_factory=lambda: InventoryEvents.INVENTORY_RESERVE_REQUESTED)
    items: list[OrderItem]


class InventoryReleaseRequested(OrderBaseEvent):
    """Event published when inventory needs to be released (compensation)"""
    event_type: str = Field(default_factory=lambda: InventoryEvents.INVENTORY_RELEASE_REQUESTED)
    items: list[OrderItem]
    reason: str

# ============== PRODUCT SAGA EVENTS ==============
class InventoryReserveSucceeded(OrderBaseEvent):
    """Event published when inventory reserve succeeds"""
    event_type: str = Field(default_factory=lambda: InventoryEvents.INVENTORY_RESERVE_SUCCEEDED)
    reserved_items: list[OrderItem]


class InventoryReserveFailed(OrderBaseEvent):
    """Event published when inventory reserve fails"""
    event_type: str = Field(default_factory=lambda: InventoryEvents.INVENTORY_RESERVE_FAILED)
    reasons: str
    failed_items: list[OrderItem]


# ============== PAYMENT SAGA EVENTS ==============
class PaymentBaseEvent(BaseEvent):
    order_id: UUID
    user_id: UUID
    user_email: EmailStr
    service: str = Field(default_factory=lambda: Services.PAYMENT_SERVICE)
    payment_intent_id: str
    amount: float
    currency: str


class PaymentAuthorizedEvent(PaymentBaseEvent):
    """The card is authorized for the order total; nothing is charged yet."""
    event_type: str = Field(default_factory=lambda: PaymentEvents.PAYMENT_AUTHORIZED)


class PaymentSucceededEvent(PaymentBaseEvent):
    """The authorized amount was captured: the customer is charged."""
    event_type: str = Field(default_factory=lambda: PaymentEvents.PAYMENT_SUCCEEDED)


class PaymentFailedEvent(PaymentBaseEvent):
    """Event published when a Stripe payment intent fails"""
    event_type: str = Field(default_factory=lambda: PaymentEvents.PAYMENT_FAILED)
    reason: str


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


class PaymentRefundFailedEvent(PaymentBaseEvent):
    """A refund order_service requested could not be made."""
    event_type: str = Field(default_factory=lambda: PaymentEvents.PAYMENT_REFUND_FAILED)
    refund_id: UUID
    reason: str


class PaymentCancelledEvent(PaymentBaseEvent):
    """Event published when a Stripe payment intent is cancelled"""
    event_type: str = Field(default_factory=lambda: PaymentEvents.PAYMENT_CANCELLED)
    reason: str


class PaymentCommandBase(BaseEvent):
    """An order_service instruction about the card held for one order."""
    order_id: UUID
    user_id: UUID
    user_email: EmailStr
    service: str = Field(default_factory=lambda: Services.ORDER_SERVICE)


class PaymentCaptureRequested(PaymentCommandBase):
    """Fulfillment is secured: charge the authorized card."""
    event_type: str = Field(default_factory=lambda: PaymentCommands.CAPTURE_REQUESTED)


class PaymentRefundRequested(PaymentCommandBase):
    """Give back part of an order's payment: chosen lines, maybe shipping."""
    event_type: str = Field(default_factory=lambda: PaymentCommands.REFUND_REQUESTED)
    refund_id: UUID
    amount_cents: int = Field(gt=0)
    reason: str


class PaymentReleaseRequested(PaymentCommandBase):
    """Money is held for an order that cannot be fulfilled: void or refund it.

    Sent when a payment lands for an order that is unknown or already
    cancelled, so a card hold can never outlive the order it was for.
    """
    event_type: str = Field(default_factory=lambda: PaymentCommands.RELEASE_REQUESTED)
    payment_intent_id: str | None = None
    reason: str


# ============== SHIPPING SAGA EVENTS ==============
class ShipmentBaseEvent(BaseEvent):
    shipment_id: UUID
    order_id: UUID
    user_id: UUID
    user_email: EmailStr
    service: str = Field(default_factory=lambda: Services.SHIPPING_SERVICE)


class ShipmentCreatedEvent(ShipmentBaseEvent):
    """Event published when a shipment is created for an order"""
    event_type: str = Field(default_factory=lambda: ShippingEvents.SHIPMENT_CREATED)
    method_id: UUID
    estimated_delivery: str


class ShipmentShippedEvent(ShipmentBaseEvent):
    """Event published when a shipment is handed to the carrier"""
    event_type: str = Field(default_factory=lambda: ShippingEvents.SHIPMENT_SHIPPED)
    tracking_number: str
    shipped_at: str


class ShipmentDeliveredEvent(ShipmentBaseEvent):
    """Event published when a shipment is delivered"""
    event_type: str = Field(default_factory=lambda: ShippingEvents.SHIPMENT_DELIVERED)
    delivered_at: str


class ShipmentCancelledEvent(ShipmentBaseEvent):
    """Event published when a shipment is cancelled"""
    event_type: str = Field(default_factory=lambda: ShippingEvents.SHIPMENT_CANCELLED)
    reason: str


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


class ProductionJobStartedEvent(ProductionJobBaseEvent):
    """Event published when the operator picks a queued job up for printing."""
    event_type: str = Field(default_factory=lambda: ProductionEvents.PRODUCTION_JOB_STARTED)


class ProductionJobPrintedEvent(ProductionJobBaseEvent):
    """Event published when the garment has been printed and is awaiting post."""
    event_type: str = Field(default_factory=lambda: ProductionEvents.PRODUCTION_JOB_PRINTED)


class ProductionJobShippedEvent(ProductionJobBaseEvent, OrderShippedBaseEvent):
    """Event published when the operator posts the finished garment."""
    event_type: str = Field(default_factory=lambda: ProductionEvents.PRODUCTION_JOB_SHIPPED)


class ProductionJobDeliveredEvent(ProductionJobBaseEvent, OrderDeliveredBaseEvent):
    """Event published when an in-house parcel is confirmed as delivered."""
    event_type: str = Field(default_factory=lambda: ProductionEvents.PRODUCTION_JOB_DELIVERED)


class ProductionJobCancelledEvent(ProductionJobBaseEvent):
    """Event published when a job leaves the queue without being fulfilled."""
    event_type: str = Field(default_factory=lambda: ProductionEvents.PRODUCTION_JOB_CANCELLED)
    reason: str
    reconciliation_required: bool = False


# ============== ARTWORK RETENTION EVENTS ==============
class ArtworkRetentionBaseEvent(BaseEvent):
    """Links a paid order line to the stored print file it depends on.

    product_service owns the artwork object while order_service owns the
    reference to it. Without this link a cleanup job sweeping unreferenced
    generation drafts cannot tell a paid order's print file from an abandoned
    preview, so it could delete artwork that still has to be printed.
    """
    service: str = Field(default_factory=lambda: Services.ORDER_SERVICE)
    order_id: UUID
    artwork_keys: list[str] = Field(default_factory=list)


class ArtworkRetainedEvent(ArtworkRetentionBaseEvent):
    """Event published when an order is confirmed and its artwork must survive."""
    event_type: str = Field(default_factory=lambda: ArtworkEvents.ARTWORK_RETAINED)


class ArtworkReleasedEvent(ArtworkRetentionBaseEvent):
    """Event published when an order is cancelled and its hold can be dropped."""
    event_type: str = Field(default_factory=lambda: ArtworkEvents.ARTWORK_RELEASED)
    reason: str = ""


# ============== WISHLIST EVENTS ==============
class WishlistItemBaseEvent(BaseEvent):
    service: str = Field(default_factory=lambda: Services.WISHLIST_SERVICE)
    user_id: UUID
    wishlist_id: UUID
    product_id: UUID


class WishlistItemAddedEvent(WishlistItemBaseEvent):
    """Event published when an item is added to a wishlist"""
    event_type: str = Field(default_factory=lambda: WishlistEvents.WISHLIST_ITEM_ADDED)


class WishlistItemRemovedEvent(WishlistItemBaseEvent):
    """Event published when an item is removed from a wishlist"""
    event_type: str = Field(default_factory=lambda: WishlistEvents.WISHLIST_ITEM_REMOVED)


# ============== SUPPLIER EVENTS ==============
class SupplierBaseEvent(BaseEvent):
    """Base class for supplier-related events."""
    service: str = Field(default_factory=lambda: Services.SUPPLIER_SERVICE)
    supplier_id: str


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
