from uuid import UUID, uuid4
from datetime import datetime, timezone

from pydantic import BaseModel, EmailStr, Field

from contracts.services_enums import Services
from contracts.event_enums import UserEvents


class BaseEvent(BaseModel):
    """Base class for all events"""
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service: str
    event_type: str
    schema_version: int = 1
    correlation_id: UUID = Field(default_factory=uuid4)


# ============== USER SAGA EVENTS ==============
class UserBaseEvent(BaseEvent):
    service: str = Field(default_factory=lambda: Services.USER_SERVICE)
    user_email: EmailStr
    user_id: UUID | None = None


class UserDeletedEvent(UserBaseEvent):
    """Event published when a user account is deleted"""
    event_type: str = Field(default_factory=lambda: UserEvents.USER_DELETED)
