from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ShippingAddress(BaseModel):
    street: str
    city: str
    province: str
    postal_code: str
    country: str = "US"

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
    name: str
    carrier: str
    base_cost: Decimal
    estimated_days: int
    is_active: bool = True


class UpdateShippingMethod(BaseModel):
    name: Optional[str] = None
    carrier: Optional[str] = None
    base_cost: Optional[Decimal] = None
    estimated_days: Optional[int] = None
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
    user_email: str = ""
    method_id: UUID
    destination: ShippingAddress


class UpdateShipment(BaseModel):
    status: Optional[str] = None
    tracking_number: Optional[str] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


class ShippingRateRequest(BaseModel):
    destination: ShippingAddress
    weight_kg: Optional[Decimal] = None
