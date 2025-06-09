from datetime import datetime
from typing import Optional, List
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

    model_config = ConfigDict(from_attributes=True, 
                              json_schema_extra={
                                "example": {
                                    "id": "dfsdfgdft5646rh",
                                    "name": "Test Test",
                                    "email": "tests@gmail.com",
                                    "hashed_password": "!dff45e",
                                    "role": "user",
                                    "phone_number": "07000000000",
                                    "date_created": "2021-04-24T11:46:07.770741"
                                }
                            },
                            json_encoders={
                                datetime: lambda v: v.isoformat(), # convert datetime to ISO format
                                UUID: lambda v: str(v), # convert UUID to string
                                EmailStr: lambda v: str(v)  # convert EmailStr to string
                            }


    )


class UserSignUp(BaseModel):
    name: str = Field(..., min_length=3, max_length=50, description="User's name")
    email: EmailStr = Field(..., description="User's email")
    password: str = Field(..., min_length=8, max_length=100,description="User's password")
    is_verified: Optional[bool] = Field(False, description="User's verification status")
    role: Optional[str] 

    model_config = ConfigDict(from_attributes=True, json_schema_extra={
        "example": {
            "name": "jhon doe",
            "email": "a.kostenkouk@gmail.com",
            "password": "12345678",
            "is_verified": True,
            "role": "admin"
        }

    })

class CurrentUserInfo(BaseModel):
    email: str
    id: UUID
    user_role: Optional[str]
    exp: Optional[int] = None

class AllUsersInfo(BaseModel):
    users: List[UserInfo]

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
    
class TokenPayload(BaseModel):
    sub: str
    exp: int 

class VerificationEmailSchema(BaseModel):
    addresses: List[str]
    
class PasswordUpdateResponse(BaseModel):
    detail: str
    email: EmailStr

class EmailSchema(BaseModel):
    email: EmailStr
    body: dict


class EmailVerificationResponse(BaseModel):
    detail: str
    email: str
    verified: bool
    

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    detail: str
    email: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str = Field(..., min_length=8)