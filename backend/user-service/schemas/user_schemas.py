from datetime import datetime
from typing import Optional, List, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr
from pydantic.fields import Field


class UserInfo(BaseModel):
    id: UUID 
    name: str = Field(..., min_length=3, max_length=50, description="User name must be between 3 and 50 characters")
    email: EmailStr = Field(..., description="User email")
    role: Optional[str]
    phone_number: Optional[str]
    image: Optional[str]
    date_created: datetime
    date_updated: Optional[datetime]
    is_verified: bool

    model_config = ConfigDict(from_attributes=True)
    


class UserSignUp(BaseModel):
    name: str = Field(..., min_length=3, max_length=50, description="User's name")
    email: EmailStr = Field(..., description="User's email")
    password: str = Field(..., min_length=8, max_length=100,description="User's password")
    is_verified: Optional[bool] = Field(False, description="User's verification status")
    role: Optional[str] = "user"

    model_config = ConfigDict(from_attributes=True)

class CurrentUserInfo(BaseModel):
    email: EmailStr
    id: UUID
    role: str | None
    


class UserSaveWithGoogle(BaseModel):
    email: str
    password: str = Field(..., min_length=8, description="User's password")


class UserUpdate(BaseModel):
    name: str
    password: str
    
    
class UserBasicUpdate(BaseModel):
    """Schema for basic user information updates"""
    name: Optional[str] = None
    phone_number: Optional[str] = None
    image: Optional[str] = None


class GetUser(BaseModel):
    email: str


class DeleteUser(BaseModel):
    email: str

class TokenSchema(BaseModel):
    access_token: str
    token_type: str
    
class UserLoginDetails(BaseModel):
    access_token: str
    token_type: str
    token_expiry: int
    user_id: UUID
    user_email: EmailStr
    user_role: str
    
class TokenPayload(BaseModel):
    sub: str
    exp: int 


    
class TokenData(BaseModel):
    token: str
    expires: datetime
    
class EmailVerificationResponse(BaseModel):
    detail: str
    email: str
    verified: bool
    
class VerificationEmailSchema(BaseModel):
    addresses: List[str]
    
class PasswordUpdateResponse(BaseModel):
    detail: str
    email: EmailStr

class EmailSchema(BaseModel):
    email: EmailStr
    body: dict



    

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    detail: str
    email: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str = Field(..., min_length=8)
    
    
class FilterParams(BaseModel):
    offset: Optional[int] = Field(None, ge=0, description="Number of users to skip")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: Optional[Literal['asc', 'desc']] = Field('asc', description="Sort order: 'asc' or 'desc'")
    limit: Optional[int] = Field(None, ge=1, le=100, description="Maximum number of users to return")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Filter by user name")
    is_active: Optional[bool] = Field(None, description="Filter by user active status")
    is_verified: Optional[bool] = Field(None, description="Filter by user verification status")
    date_created: Optional[datetime] = Field(None, description="Filter by user creation date")
    date_updated: Optional[datetime] = Field(None, description="Filter by user update date")
    date_created_from: Optional[datetime] = Field(None, description="Filter users created from this date")
    date_created_to: Optional[datetime] = Field(None, description="Filter users created up to this date")
    date_updated_from: Optional[datetime] = Field(None, description="Filter users updated from this date")
    date_updated_to: Optional[datetime] = Field(None, description="Filter users updated up to this date")
