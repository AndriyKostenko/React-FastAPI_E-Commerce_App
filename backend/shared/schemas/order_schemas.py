from pydantic import BaseModel

from schemas.product_schemas import ProductSchema


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


class CreateOrder(BaseModel):
    amount: float
    currency: str
    status: str
    delivery_status: str
    payment_intent_id: str
    products: list[ProductSchema]
    address: list[AddressType]
    user_id: str


class UpdateOrder(BaseModel):
    delivery_status: str | None = None
    status: str | None = None
    amount: float


class PaymentIntentRequest(BaseModel):
    items: list[ProductSchema]
    payment_intent_id: str | None
