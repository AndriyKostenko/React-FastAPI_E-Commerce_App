from typing import Optional, List

from pydantic import BaseModel

from schemas.product_schemas import ProductSchema # type: ignore


class OrderSchema(BaseModel):
    id: str
    amount: float
    currency: str
    status: str
    delivery_status: str
    payment_intent_id: str
    products: List[ProductSchema]

class CreateOrder(BaseModel):
    amount: float
    currency: str
    status: str
    delivery_status: str
    payment_intent_id: str
    products: List[ProductSchema]
    address: List[AddressType]
    user_id: str


class UpdateOrder(BaseModel):
    delivery_status: Optional[str] = None
    status: Optional[str] = None
    amount: float


class PaymentIntentRequest(BaseModel):
    items: List[ProductSchema]
    payment_intent_id: Optional[str]


class AddressType(BaseModel):
    street: str
    city: str
    province: str
    postal_code: str
