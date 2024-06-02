from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict
from pydantic.fields import Field


class SelectedImgType(BaseModel):
    color: str
    colorCode: str
    image: str


class CartProductType(BaseModel):
    id: str
    name: str
    description: str
    category: str
    brand: str
    selectedImg: SelectedImgType
    quantity: int
    price: float


class CreateOrder(BaseModel):
    amount: float
    currency: str
    status: str
    delivery_status: str
    create_date: datetime
    payment_intent_id: str
    products: List[CartProductType]
    # TODO: need to check how and where to add address
    # address: List[AddressType]
    user_id: int


class UpdateOrder(BaseModel):
    amount: float
    payment_intent_id: str
    items: List[CartProductType]


class PaymentIntentRequest(BaseModel):
    items: List[CartProductType]
    payment_intent_id: Optional[str]
