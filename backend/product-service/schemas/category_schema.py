from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CategoryBase(BaseModel):
    """Base category schema with common attributes"""
    name: str
    image_url: Optional[str] = None


class CreateCategory(CategoryBase):
    """Schema for creating a new category"""
    pass


class UpdateCategory(CategoryBase):
    """Schema for updating an existing category"""
    name: Optional[str] = None  # Make name optional for updates
    delivery_status: Optional[str] = None
    status: Optional[str] = None
    amount: Optional[float] = None


class CategorySchema(CategoryBase):
    """Schema for category responses"""
    id: UUID
    date_created: datetime
    date_updated: Optional[datetime] = None

    class Config:
        from_attributes = True



