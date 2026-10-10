"""What the back office sees of shipping-service's tables (see shared.admin.admin_tables)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ShipmentAdminSchema(BaseModel):
    id: UUID
    order_id: UUID
    user_id: UUID
    method_id: UUID
    tracking_number: str | None
    status: str
    estimated_delivery: datetime | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    date_created: datetime
    date_updated: datetime | None
