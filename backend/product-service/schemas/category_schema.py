from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, HttpUrl


class CategoryBase(BaseModel):
    """Base category schema with common attributes"""
    name: str
    image_url: HttpUrl
    
    # adding config for model serialization from ORM attributes
    model_config = ConfigDict(from_attributes=True)


class CreateCategory(BaseModel):
    """Schema for creating a new category - internal use after file processing"""
    name: str
    image_url: Optional[HttpUrl] = None


class UpdateCategory(BaseModel):
    """Schema for updating an existing category"""
    name: Optional[str] = None
    image_url: Optional[HttpUrl] = None


class CategorySchema(CategoryBase):
    """Schema for category responses"""
    id: UUID
    date_created: datetime
    date_updated: Optional[datetime] = None
    
class CategoriesFilterParams(BaseModel):
    """Schema for filtering categories - currently unused but can be extended"""
    name: Optional[str] = None


