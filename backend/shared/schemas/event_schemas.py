from uuid import UUID
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class BaseEvent(BaseModel):
    """Base class for all events"""
    event_id: UUID
    timestamp: datetime
    service: str
    event_type: str
    
class UserRegisteredEvent(BaseEvent):
    """Event published when a user registers"""
    email: EmailStr
    token: str
    
class UserLoginEvent(BaseEvent):
    """Event published when a user logs in"""
    email: EmailStr
    
class PasswordResetRequestedEvent(BaseEvent):
    """Event published when password reset is requested"""
    email: EmailStr
    reset_token: str
    
class PasswordResetSuccessEvent(BaseEvent):
    """Event published when pussword reset success"""
    email: EmailStr
    
class EmailVerificationRequestedEvent(BaseEvent):
    """Event published when email verification is requested"""
    email: EmailStr
    verification_token: Optional[str] = None
    event_type: str 

