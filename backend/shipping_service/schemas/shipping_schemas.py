from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from contracts.limits import Code, Money


# The same bounds as an address saved in the account (user-service's AddressInput).
class ShippingAddress(BaseModel):
    street: str = Field(max_length=255)
    city: str = Field(max_length=100)
    province: str = Field(max_length=64)
    postal_code: str = Field(max_length=10)
    country: str = Field(default="US", max_length=64)

    model_config = ConfigDict(from_attributes=True)


class ShippingMethodSchema(BaseModel):
    id: UUID
    name: str
    carrier: str
    base_cost: Decimal
    estimated_days: int
    is_active: bool
    date_created: datetime
    date_updated: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CreateShippingMethod(BaseModel):
    # shipping_methods.name and .carrier are String(100).
    name: str = Field(min_length=1, max_length=100)
    carrier: str = Field(min_length=1, max_length=100)
    base_cost: Money
    estimated_days: int = Field(ge=0, le=365)
    is_active: bool = True


class UpdateShippingMethod(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    carrier: Optional[str] = Field(None, min_length=1, max_length=100)
    base_cost: Optional[Money] = None
    estimated_days: Optional[int] = Field(None, ge=0, le=365)
    is_active: Optional[bool] = None


class ShipmentSchema(BaseModel):
    id: UUID
    order_id: UUID
    user_id: UUID
    method_id: UUID
    tracking_number: Optional[str] = None
    status: str
    estimated_delivery: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    date_created: datetime
    date_updated: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CreateShipment(BaseModel):
    order_id: UUID
    user_id: UUID
    user_email: str = Field(default="", max_length=320)
    method_id: UUID
    destination: ShippingAddress


class UpdateShipment(BaseModel):
    status: Optional[Code] = None
    # shipments.tracking_number is String(100).
    tracking_number: Optional[str] = Field(None, max_length=100)
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


class ShippingRateRequest(BaseModel):
    destination: ShippingAddress
    weight_kg: Optional[Decimal] = Field(None, gt=0, le=1000)
