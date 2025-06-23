from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CategoryBase(BaseModel):
    """Base category schema with common attributes"""
    name: str
    image_url: Optional[str] = None
    
    # adding config for model serialization from ORM attributes
    model_config = ConfigDict(from_attributes=True)


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


class AllCategories(BaseModel):
    """Schema for returning a list of categories"""
    categories: List[CategorySchema]
    
    model_config = ConfigDict(from_attributes=True)