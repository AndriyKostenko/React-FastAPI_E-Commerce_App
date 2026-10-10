"""What the back office sees of notification-service's tables (see shared.admin.admin_tables)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationAdminSchema(BaseModel):
    id: UUID
    user_id: UUID | None
    notification_type: str
    message: str
    is_read: bool
    date_created: datetime
