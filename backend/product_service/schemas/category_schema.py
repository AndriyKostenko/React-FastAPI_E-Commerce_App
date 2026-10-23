from datetime import datetime
from typing import Optional, List, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from contracts.limits import NAME_MAX_LENGTH, Identifier, Url

from storage.catalogue_url import CatalogueImageUrl


class CategoryBase(BaseModel):
    """Base category schema with common attributes"""
    name: str
    cj_category_id: Optional[str] = None
    image_url: Optional[CatalogueImageUrl] = None

    # adding config for model serialization from ORM attributes
    model_config = ConfigDict(from_attributes=True)


class CreateCategory(BaseModel):
    """Schema for creating a new category - internal use after file processing"""
    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    cj_category_id: Optional[Identifier] = None
    image_url: Optional[Union[HttpUrl, Url]] = None


class UpdateCategory(BaseModel):
    """Schema for updating an existing category"""
    name: Optional[str] = Field(None, min_length=1, max_length=NAME_MAX_LENGTH)
    cj_category_id: Optional[Identifier] = None
    image_url: Optional[HttpUrl] = None


class CategorySchema(CategoryBase):
    """Schema for category responses"""
    id: UUID
    date_created: datetime
    date_updated: Optional[datetime] = None


class CategoriesFilterParams(BaseModel):
    """Schema for filtering categories - currently unused but can be extended"""
    name: Optional[str] = Field(None, max_length=NAME_MAX_LENGTH)
