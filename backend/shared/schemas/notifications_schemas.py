from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Any, List


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


class NotificationsFilterParams(BaseModel):
    is_read: bool | None = None
    notification_type: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort_by: str = "date_created"
    sort_order: str = "desc"
    date_created_from: datetime | None = None
    date_created_to: datetime | None = None
