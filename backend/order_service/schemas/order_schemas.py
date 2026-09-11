from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import Any, Optional

from pydantic import BaseModel, PositiveFloat, PositiveInt, ConfigDict, EmailStr, Field, computed_field, model_validator

from shared.contracts.order import CustomTshirtSpecification, FulfillmentType
from shared.utils.money import to_cents


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

class OrderAddressBase(AddressType):
    id: UUID
    user_id: UUID

class OrderProductItem(BaseModel):
    id: UUID | None = None
    variant_id: UUID | None = None
    name: str | None = None
    price: Decimal | None = None
    quantity: PositiveInt = Field(le=99)
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
    amount: PositiveFloat | None = None
    currency: str = "cad"
    payment_intent_id: str | None = None
    products: list[OrderProductItem] = Field(min_length=1, max_length=50)
    address: AddressType
    shipping_logistic_name: str | None = Field(default=None, max_length=200)


class QuoteOrderRequest(BaseModel):
    products: list[OrderProductItem] = Field(min_length=1, max_length=50)
    address: AddressType
    shipping_logistic_name: str | None = Field(default=None, max_length=200)


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
    delivery_status: str | None = None
    cj_order_number: str | None = None


class CancelOrder(BaseModel):
    reason: str

class PaymentIntentRequest(BaseModel):
    items: list[OrderProductItem]
    payment_intent_id: str | None
