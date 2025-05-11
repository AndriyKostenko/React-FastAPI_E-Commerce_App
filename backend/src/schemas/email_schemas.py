from pydantic import BaseModel, EmailStr
from typing import List, Dict, Any
from pydantic.fields import Field

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