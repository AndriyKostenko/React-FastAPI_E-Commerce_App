"""Order payload fragments embedded in cross-service events."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, PositiveFloat, PositiveInt


class OrderItem(BaseModel):
    order_id: UUID
    product_id: UUID
    variant_id: UUID | None = None
    quantity: PositiveInt
    price: PositiveFloat

    model_config = ConfigDict(from_attributes=True)


class ConfirmedOrderItem(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    quantity: int
    price: PositiveFloat

    model_config = ConfigDict(from_attributes=True)


class ConfirmedOrderAddress(BaseModel):
    street: str
    city: str
    province: str
    postal_code: str
    country: str | None = None
    country_code: str | None = None
    name: str | None = None
    phone: str | None = None

    model_config = ConfigDict(from_attributes=True)
