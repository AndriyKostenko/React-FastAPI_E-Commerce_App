from uuid import UUID, uuid4
from datetime import datetime, timezone

from pydantic import BaseModel, EmailStr, Field

from contracts.services_enums import Services
from contracts.event_enums import UserEvents
from contracts.limits import Code, Token


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


class UserRegisteredEvent(UserBaseEvent):
    """Event published when a user registers"""
    event_type: Code = Field(default_factory=lambda: UserEvents.USER_REGISTERED)
    token: Token


class UserLoginEvent(UserBaseEvent):
    """Event published when a user logs in"""
    event_type: Code = Field(default_factory=lambda: UserEvents.USER_LOGGED_IN)


class PasswordResetRequestedEvent(UserBaseEvent):
    """Event published when password reset is requested"""
    event_type: Code = Field(default_factory=lambda: UserEvents.USER_PASSWORD_RESET_REQUEST)
    reset_token: Token


class PasswordResetSuccessEvent(UserBaseEvent):
    """Event published when pussword reset success"""
    event_type: Code = Field(default_factory=lambda: UserEvents.USER_PASSWORD_RESET_SUCCESS)


class ExistingAccountRegistrationEvent(UserBaseEvent):
    """Event published when someone registers with the email of a verified account.

    The sign-up form answers the same either way (it must not reveal who has
    an account), so the owner is told by email instead.
    """
    event_type: Code = Field(default_factory=lambda: UserEvents.USER_REGISTRATION_EXISTING)


class EmailVerificationEvent(UserBaseEvent):
    """Event published when email verification is proceeded"""
    event_type: Code = Field(default_factory=lambda: UserEvents.USER_EMAIL_VERIFIED)


class UserDeletedEvent(UserBaseEvent):
    """Event published when a user account is deleted"""
    event_type: Code = Field(default_factory=lambda: UserEvents.USER_DELETED)
