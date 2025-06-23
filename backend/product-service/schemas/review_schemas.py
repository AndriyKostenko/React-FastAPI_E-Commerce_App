from datetime import datetime
from pyexpat import model
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, ConfigDict



class UserInfo(BaseModel):
    id: UUID 
    name: str
    email: EmailStr 
    role: Optional[str]
    phone_number: Optional[str]
    image: Optional[str]
    date_created: datetime
    date_updated: Optional[datetime]
    is_verified: bool
    
    model_config = ConfigDict(from_attributes=True)

class ReviewBase(BaseModel):
    """Base review schema with common attributes"""
    product_id: UUID
    user_id: UUID
    comment: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5)  # Rating between 0 and 5


class CreateReview(ReviewBase):
    """Schema for creating a new review"""
    pass


class UpdateReview(ReviewBase):
    """Schema for updating an existing review"""
    product_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    comment: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5)


class ReviewSchema(ReviewBase):
    """Schema for review responses"""
    id: UUID
    date_created: datetime
    date_updated: Optional[datetime] = None
    user: UserInfo

class AllReviewsSchema(BaseModel):
    """Schema for returning all reviews for a product"""
    reviews: list[ReviewSchema]

    model_config = ConfigDict(from_attributes=True)
