from typing import Optional

from pydantic import BaseModel, EmailStr, validator
from pydantic.fields import Field
from fastapi import HTTPException, Form


class UserInfo(BaseModel):
    id: int
    name: str
    email: str
    role: str = Optional[str]

    class Config:
        from_attributes = True


class UserSignUp(BaseModel):
    name: str
    email: str
    password: str = Field(example='password', min_length=8)


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
