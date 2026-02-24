from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, PositiveFloat, PositiveInt, ConfigDict, EmailStr


class OrderSchema(BaseModel):
    id: UUID
    user_id: UUID
    user_email: EmailStr
    amount: PositiveFloat
    currency: str
    status: str
    delivery_status: str
    payment_intent_id: str

    model_config = ConfigDict(from_attributes=True)

class AddressType(BaseModel):
    street: str
    city: str
    province: str
    postal_code: str

    model_config = ConfigDict(from_attributes=True)

class OrderAddressBase(AddressType):
    id: UUID
    user_id: UUID

class OrderProductItem(BaseModel):
    id: UUID
    name: str
    price: Decimal
    quantity: PositiveInt

    model_config = ConfigDict(from_attributes=True)


class CreateOrder(BaseModel):
    user_id: UUID
    user_email: EmailStr
    amount: PositiveFloat
    currency: str
    payment_intent_id: str
    products: list[OrderProductItem]
    address: AddressType

class OrderItemBase(BaseModel):
    order_id: UUID
    product_id: UUID
    quantity: PositiveInt
    price: PositiveFloat

    model_config = ConfigDict(from_attributes=True)

class UpdateOrder(BaseModel):
    delivery_status: str | None = None
    status: str | None = None
    amount: float

class PaymentIntentRequest(BaseModel):
    items: list[OrderProductItem]
    payment_intent_id: str | None
