from datetime import datetime
from typing import Optional, List
from unittest.mock import Base
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CategoryBase(BaseModel):
    """Base category schema with common attributes"""
    name: str
    image_url: str
    
    # adding config for model serialization from ORM attributes
    model_config = ConfigDict(from_attributes=True)


class CreateCategory(BaseModel):
    """Schema for creating a new category - internal use after file processing"""
    name: str
    image_url: str


class UpdateCategory(BaseModel):
    """Schema for updating an existing category"""
    name: Optional[str] = None
    image_url: Optional[str] = None


class CategorySchema(CategoryBase):
    """Schema for category responses"""
    id: UUID
    date_created: datetime
    date_updated: Optional[datetime] = None


