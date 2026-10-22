from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import Any, Optional

from pydantic import BaseModel, PositiveFloat, PositiveInt, ConfigDict, EmailStr, Field, computed_field, model_validator

from contracts.limits import LINES_MAX, MONEY_MAX, Code, Identifier, LineQuantity, Money, Name, Text
from contracts.order import CustomTshirtSpecification, FulfillmentType
from contracts.shipping_region import CanadianAddress, NotShippableError
from utils.money import to_cents


class ShippingOption(BaseModel):
    """One way to ship the CJ part of a cart, priced in the order currency."""

    logistic_name: str
    amount: Decimal
    # CJ's own USD price, kept so fulfillment can check what CJ later bills.
    # Excluded from serialization: the customer never sees our costs.
    cost_usd: Decimal = Field(exclude=True)
    delivery_time: str | None = None


class OrderSchema(BaseModel):
    id: UUID
    user_id: UUID
    user_email: EmailStr
    amount: PositiveFloat
    subtotal_amount: Decimal | None = None
    shipping_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    tax_calculation_id: str | None = None
    dispute_status: str | None = None
    shipping_logistic_name: str | None = None
    currency: str
    status: str
    delivery_status: str
    payment_intent_id: str | None = None
    address_id: UUID
    cj_order_number: str | None = None
    date_created: datetime
    date_updated: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def amount_cents(self) -> int:
        """The total in minor units: the only form money leaves this service in."""
        return to_cents(self.amount)

class AddressType(BaseModel):
    street: str
    city: str
    province: str
    postal_code: str
    country: str | None = None
    country_code: str | None = None
    name: str | None = None
    phone: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ParcelView(BaseModel):
    """The parcel one order line left in."""

    tracking_number: str
    carrier: str | None = None
    tracking_url: str | None = None
    shipped_at: datetime | None = None


class OrderLineView(BaseModel):
    """One line of an order as its customer sees it: what, how many, and where it is."""

    order_item_id: UUID
    product_id: UUID
    variant_id: UUID | None = None
    product_name: str
    quantity: int
    unit_price: Decimal
    fulfillment_type: str
    status: str
    delivered_at: datetime | None = None
    parcel: ParcelView | None = None


class OrderDetailSchema(OrderSchema):
    """An order with its shipping address and each line's progress and tracking."""

    address: AddressType | None = None
    lines: list[OrderLineView]


class ShippingAddress(AddressType):
    """
    A shipping address the customer submits: Canadian, or refused with a 422.

    Checked here, before anything is priced, charged or sent to CJ, so an order
    the store cannot fulfil is never paid for. Stored addresses are read back
    through ``AddressType`` unchanged.
    """

    # The same bounds as an address saved in the account (user-service's AddressInput).
    street: str = Field(max_length=255)
    city: str = Field(max_length=100)
    province: str = Field(max_length=64)
    postal_code: str = Field(max_length=10)
    country: str | None = Field(default=None, max_length=64)
    country_code: str | None = Field(default=None, max_length=2)
    name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def _canadian(self) -> "ShippingAddress":
        try:
            canadian = CanadianAddress.normalise(
                country=self.country,
                country_code=self.country_code,
                province=self.province,
                postal_code=self.postal_code,
            )
        except NotShippableError as exc:
            raise ValueError(str(exc)) from exc
        self.country = canadian.country
        self.country_code = canadian.country_code
        self.province = canadian.province_code
        self.postal_code = canadian.postal_code
        return self


class OrderAddressBase(AddressType):
    id: UUID
    user_id: UUID

class OrderProductItem(BaseModel):
    id: UUID | None = None
    variant_id: UUID | None = None
    name: Name | None = None
    # Ignored: every line is priced here, never by the caller.
    price: Money | None = None
    quantity: LineQuantity
    fulfillment_type: FulfillmentType | None = None
    customization: CustomTshirtSpecification | None = None

    @model_validator(mode="after")
    def validate_identity(self):
        if self.fulfillment_type == "custom":
            if self.customization is None:
                raise ValueError("customization is required for custom order items")
        elif self.id is None:
            raise ValueError("id is required for catalog order items")
        return self

    model_config = ConfigDict(from_attributes=True)


class CreateOrder(BaseModel):
    id: UUID | None = None
    user_id: UUID
    user_email: EmailStr
    amount: PositiveFloat | None = Field(default=None, le=float(MONEY_MAX))
    # ISO 4217, as orders.currency stores it.
    currency: str = Field(default="cad", min_length=3, max_length=3)
    payment_intent_id: Identifier | None = None
    products: list[OrderProductItem] = Field(min_length=1, max_length=LINES_MAX)
    address: ShippingAddress
    shipping_logistic_name: Name | None = None


class QuoteOrderRequest(BaseModel):
    products: list[OrderProductItem] = Field(min_length=1, max_length=LINES_MAX)
    address: ShippingAddress
    shipping_logistic_name: Name | None = None


class PriceItemsRequest(BaseModel):
    products: list[OrderProductItem] = Field(min_length=1, max_length=LINES_MAX)


class PricedItem(BaseModel):
    # None only for a custom line sent without an id that cannot be sold.
    product_id: UUID | None
    variant_id: UUID | None = None
    quantity: int
    # None when the line cannot be bought as it is; see unavailable_reason.
    unit_price: Decimal | None
    available: bool = True
    unavailable_reason: str | None = None


class PriceItemsResponse(BaseModel):
    """Cart lines priced as an order would price them, in the request's order.

    A line that cannot be sold comes back with ``available`` false and the
    reason; ``subtotal_amount`` counts the available lines only.
    """

    currency: str
    items: list[PricedItem]
    subtotal_amount: Decimal


class QuoteOrderResponse(BaseModel):
    subtotal_amount: Decimal
    shipping_amount: Decimal
    tax_amount: Decimal
    amount: Decimal
    amount_cents: int
    currency: str
    products: list[dict[str, Any]]
    shipping_options: list[ShippingOption]
    shipping_logistic_name: str | None = None

class OrderItemBase(BaseModel):
    order_id: UUID
    product_id: UUID
    variant_id: UUID | None = None
    quantity: PositiveInt
    price: PositiveFloat
    fulfillment_type: FulfillmentType = "catalog"
    product_name: str | None = None
    customization: CustomTshirtSpecification | None = None
    variant_snapshot: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)

class ConfirmedOrderItem(BaseModel):
    """Item carried on OrderConfirmedEvent for downstream fulfillment."""
    product_id: UUID
    variant_id: UUID | None = None
    quantity: int
    price: PositiveFloat
    fulfillment_type: FulfillmentType = "catalog"
    product_name: str | None = None
    customization: CustomTshirtSpecification | None = None
    variant_snapshot: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class ConfirmedOrderAddress(BaseModel):
    """Address carried on OrderConfirmedEvent for downstream fulfillment."""
    street: str
    city: str
    province: str
    postal_code: str
    country: str | None = None
    country_code: str | None = None
    name: str | None = None
    phone: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UpdateOrder(BaseModel):
    delivery_status: Code | None = None
    cj_order_number: Identifier | None = None


class CancelOrder(BaseModel):
    reason: Text

class PaymentIntentRequest(BaseModel):
    items: list[OrderProductItem] = Field(max_length=LINES_MAX)
    payment_intent_id: Identifier | None
