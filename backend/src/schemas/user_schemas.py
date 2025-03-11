from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr
from pydantic.fields import Field


class UserInfo(BaseModel):
    id: UUID = Field(..., description="User ID is required", example="123e4567-e89b-12d3-a456-426614174000")
    name: str = Field(..., min_length=3, max_length=50, description="User name must be between 3 and 50 characters")
    email: EmailStr = Field(..., description="User email")
    role: Optional[str] = Field(None, description="User role", example="user , admin")
    phone_number: Optional[str] = Field(None, description="User phone number", example="07000000000", min_length=10, max_length=15)
    date_created: datetime
    image: Optional[str] = Field(None, description="User image URL", example="https://example.com/image.jpg")
    date_updated: Optional[datetime] 

    model_config = ConfigDict(from_attributes=True, json_schema_extra={
        "example": {
            "id": "dfsdfgdft5646rh",
            "name": "Test Test",
            "email": "tests@gmail.com",
            "hashed_password": "!dff45e",
            "role": "user",
            "phone_number": "07000000000",
            "date_created": "2021-04-24T11:46:07.770741"
        }

    })


class UserSignUp(BaseModel):
    name: str = Field(..., min_length=3, max_length=50, description="User's name")
    email: EmailStr = Field(..., description="User's email")
    password: str = Field(..., min_length=8, max_length=100,description="User's password")

    model_config = ConfigDict(from_attributes=True, json_schema_extra={
        "example": {
            "name": "jhon doe",
            "email": "jhondoe@gmail.com",
            "password": "12345678"
        }

    })


class UserSaveWithGoogle(BaseModel):
    email: str
    password: str = Field(..., min_length=8, description="User's password")


class UserUpdate(BaseModel):
    name: str
    password: str


class GetUser(BaseModel):
    email: str


class DeleteUser(BaseModel):
    email: str


class TokenSchema(BaseModel):
    access_token: str = Field(..., description="Access token", min_length=1)
    token_type: str
    
class UserLoginDetails(BaseModel):
    access_token: str
    token_type: str
    user_role: Optional[str]
    token_expiry: int
    user_id: UUID
    
class TokenPayload(BaseModel):
    sub: str = None
    exp: int = None
