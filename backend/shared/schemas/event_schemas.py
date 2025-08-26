from uuid import UUID
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class BaseEvent(BaseModel):
    """Base class for all events"""
    event_id: UUID
    timestamp: datetime
    service: str


class UserRegisteredEvent(BaseEvent):
    """Event published when a user registers"""
    user_id: UUID
    email: EmailStr
    role: str
    token: str
 
    

class UserLoginEvent(BaseEvent):
    """Event published when a user logs in"""
    user_id: UUID
    email: EmailStr
    role: str  


class PasswordResetRequestedEvent(BaseEvent):
    """Event published when password reset is requested"""
    user_id: UUID
    email: EmailStr
    reset_token: str
    event_type: str 


class EmailVerificationRequestedEvent(BaseEvent):
    """Event published when email verification is requested"""
    user_id: UUID
    email: EmailStr
    verification_token: Optional[str] = None
    event_type: str 

