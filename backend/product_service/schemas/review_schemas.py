from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# Long enough for a genuinely detailed review, short enough that one request
# cannot push an unbounded blob into the database.
REVIEW_COMMENT_MAX_LENGTH: int = 5_000


class ReviewBase(BaseModel):
    """Base review schema with common attributes"""
    product_id: UUID
    user_id: UUID
    comment: Optional[str] = Field(None, max_length=REVIEW_COMMENT_MAX_LENGTH)
    rating: Optional[float] = Field(None, ge=0, le=5)  # Rating between 0 and 5
    
    model_config = ConfigDict(from_attributes=True)


class CreateReview(BaseModel):
    comment: Optional[str] = Field(None, max_length=REVIEW_COMMENT_MAX_LENGTH)
    rating: Optional[float] = Field(None, ge=0, le=5)
    
    model_config = ConfigDict(from_attributes=True)


class UpdateReview(BaseModel):
    comment: Optional[str] = Field(None, max_length=REVIEW_COMMENT_MAX_LENGTH)
    rating: Optional[float] = Field(None, ge=0, le=5)
    
    model_config = ConfigDict(from_attributes=True)


class ReviewSchema(ReviewBase):
    """Schema for review responses"""
    id: UUID
    date_created: datetime
    date_updated: Optional[datetime] = None


