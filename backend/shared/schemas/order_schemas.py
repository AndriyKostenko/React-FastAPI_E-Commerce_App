from uuid import UUID

from pydantic import BaseModel, PositiveFloat, PositiveInt

from shared.schemas.product_schemas import ProductSchema


class OrderSchema(BaseModel):
    id: str
    amount: float
    currency: str
    status: str
    delivery_status: str
    payment_intent_id: str
    products: list[ProductSchema]


class AddressType(BaseModel):
    street: str
    city: str
    province: str
    postal_code: str

class OrderAddressBase(AddressType):
    id: UUID
    user_id: UUID


class CreateOrder(BaseModel):
    amount: float
    currency: str
    status: str
    delivery_status: str
    payment_intent_id: str
    products: list[ProductSchema]
    address: AddressType
    user_id: UUID

class OrderItemBase(BaseModel):
    order_id: UUID
    product_id: UUID
    quantity: PositiveInt
    price: PositiveFloat


class UpdateOrder(BaseModel):
    delivery_status: str | None = None
    status: str | None = None
    amount: float


class PaymentIntentRequest(BaseModel):
    items: list[ProductSchema]
    payment_intent_id: str | None
