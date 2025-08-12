from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional


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