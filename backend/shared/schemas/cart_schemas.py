from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, ConfigDict, PositiveInt


class CartItemSchema(BaseModel):
    id: UUID
    cart_id: UUID
    product_id: UUID
    quantity: PositiveInt
    price_snapshot: Decimal
    date_created: datetime
    date_updated: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CartSchema(BaseModel):
    id: UUID
    user_id: UUID
    items: list[CartItemSchema]
    date_created: datetime
    date_updated: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AddCartItem(BaseModel):
    product_id: UUID
    quantity: PositiveInt = 1
    price_snapshot: Decimal


class UpdateCartItem(BaseModel):
    quantity: PositiveInt


class CartSummary(BaseModel):
    id: UUID
    user_id: UUID
    total_items: int
    total_amount: Decimal
    items: list[CartItemSchema]
