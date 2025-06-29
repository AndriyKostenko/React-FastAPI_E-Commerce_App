from datetime import datetime
from pyexpat import model
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class ReviewBase(BaseModel):
    """Base review schema with common attributes"""
    product_id: UUID
    user_id: UUID
    comment: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5)  # Rating between 0 and 5
    
    model_config = ConfigDict(from_attributes=True)


class CreateReview(ReviewBase):
    """Schema for creating a new review"""
    pass


class UpdateReview(ReviewBase):
    """Schema for updating an existing review"""
    product_id: UUID
    user_id: UUID
    comment: Optional[str] 
    rating: Optional[float] = Field(None, ge=0, le=5)


class ReviewSchema(ReviewBase):
    """Schema for review responses"""
    id: UUID
    date_created: datetime
    date_updated: Optional[datetime] = None


