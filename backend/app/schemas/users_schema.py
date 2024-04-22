from pydantic import BaseModel, EmailStr, validator
from pydantic.fields import Field
from fastapi import HTTPException, Form



class UserInfo(BaseModel):
    name: str
    surname: str
    email: EmailStr
    class Config:
        from_attributes = True


class UserSignUp(BaseModel):
    name: str
    email: str
    password: str = Field(example='password', min_length=8)
    repeatedPassword: str = Field(example='password')




class TokenSchema(BaseModel):
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    sub: str = None
    exp: int = None