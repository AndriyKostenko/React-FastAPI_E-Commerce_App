from uuid import UUID, uuid4
from datetime import datetime, timezone

from pydantic import BaseModel, EmailStr, Field

from contracts.services_enums import Services
from contracts.event_enums import UserEvents
from contracts.limits import Code


class BaseEvent(BaseModel):
    """Base class for all events"""
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service: Code
    event_type: Code
    schema_version: int = Field(default=1, ge=1, le=1000)
    correlation_id: UUID = Field(default_factory=uuid4)


# ============== USER SAGA EVENTS ==============
class UserBaseEvent(BaseEvent):
    service: Code = Field(default_factory=lambda: Services.USER_SERVICE)
    user_email: EmailStr
    user_id: UUID | None = None


class UserDeletedEvent(UserBaseEvent):
    """Event published when a user account is deleted"""
    event_type: Code = Field(default_factory=lambda: UserEvents.USER_DELETED)
