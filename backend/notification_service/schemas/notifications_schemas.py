from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Any, List

from contracts.limits import COUNT_MAX, Code


class VerificationEmailSchema(BaseModel):
    addresses: List[str]

class PasswordUpdateResponse(BaseModel):
    detail: str
    email: EmailStr

class EmailSchema(BaseModel):
    email: EmailStr
    body: dict[str, Any]

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    detail: str
    email: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str = Field(..., min_length=8)


# ─── Notification read schemas ────────────────────────────────────────────────

class NotificationInfo(BaseModel):
    id: UUID
    user_id: UUID | None
    message: str
    notification_type: str
    is_read: bool
    date_created: datetime
    date_updated: datetime | None = None
    
    model_config = ConfigDict(from_attributes=True)


# The columns a list can be sorted by; any other name would reach getattr() on the model.
NOTIFICATION_SORT_FIELDS: str = "^(date_created|date_updated|notification_type|is_read)$"


class NotificationsFilterParams(BaseModel):
    is_read: bool | None = None
    notification_type: Code | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0, le=COUNT_MAX)
    sort_by: str = Field(default="date_created", pattern=NOTIFICATION_SORT_FIELDS)
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
    date_created_from: datetime | None = None
    date_created_to: datetime | None = None


class UnreadCountResponse(BaseModel):
    user_id: str
    unread_count: int


class BulkMarkReadResponse(BaseModel):
    updated: int
