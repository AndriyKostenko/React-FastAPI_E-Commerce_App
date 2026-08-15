from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, ConfigDict, PositiveInt, computed_field


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
    items: list[CartItemSchema]

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def total_items(self) -> int:
        return sum(item.quantity for item in self.items)

    @computed_field
    @property
    def total_amount(self) -> Decimal:
        return sum(
            (Decimal(item.quantity) * item.price_snapshot for item in self.items),
            Decimal(0),
        )
