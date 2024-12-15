from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict
from pydantic.fields import Field


class UserInfo(BaseModel):
    id: str
    name: str
    email: str
    role: Optional[str] = None
    phone_number: Optional[str] = None
    date_created: datetime
    image: Optional[str] = None

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
    name: str
    email: str
    password: str = Field(..., min_length=8, description="User's password")

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
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    sub: str = None
    exp: int = None
