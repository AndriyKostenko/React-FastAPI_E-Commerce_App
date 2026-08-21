from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import Any, Optional

from pydantic import BaseModel, PositiveFloat, PositiveInt, ConfigDict, EmailStr, Field, model_validator

from shared.contracts.order import CustomTshirtSpecification, FulfillmentType


class OrderSchema(BaseModel):
    id: UUID
    user_id: UUID
    user_email: EmailStr
    amount: PositiveFloat
    currency: str
    status: str
    delivery_status: str
    payment_intent_id: str | None = None
    address_id: UUID
    cj_order_number: str | None = None
    date_created: datetime
    date_updated: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

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


class QuoteOrderRequest(BaseModel):
    products: list[OrderProductItem] = Field(min_length=1, max_length=50)


class QuoteOrderResponse(BaseModel):
    amount: Decimal
    currency: str
    products: list[dict[str, Any]]

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
