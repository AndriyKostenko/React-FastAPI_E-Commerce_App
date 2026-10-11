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


class UserRegisteredEvent(UserBaseEvent):
    """Event published when a user registers"""
    event_type: str = Field(default_factory=lambda: UserEvents.USER_REGISTERED)
    token: str


class UserLoginEvent(UserBaseEvent):
    """Event published when a user logs in"""
    event_type: str = Field(default_factory=lambda: UserEvents.USER_LOGGED_IN)


class PasswordResetRequestedEvent(UserBaseEvent):
    """Event published when password reset is requested"""
    event_type: str = Field(default_factory=lambda: UserEvents.USER_PASSWORD_RESET_REQUEST)
    reset_token: str


class PasswordResetSuccessEvent(UserBaseEvent):
    """Event published when pussword reset success"""
    event_type: str = Field(default_factory=lambda: UserEvents.USER_PASSWORD_RESET_SUCCESS)


class EmailVerificationEvent(UserBaseEvent):
    """Event published when email verification is proceeded"""
    event_type: str = Field(default_factory=lambda: UserEvents.USER_EMAIL_VERIFIED)


class UserDeletedEvent(UserBaseEvent):
    """Event published when a user account is deleted"""
    event_type: str = Field(default_factory=lambda: UserEvents.USER_DELETED)
