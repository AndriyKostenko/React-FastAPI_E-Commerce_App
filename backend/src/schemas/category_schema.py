from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.fields import Field


class CategoryProps(BaseModel):
    id: UUID
    name: str
    image_url: str
    date_created: datetime
    date_updated: Optional[datetime] = None


class CreateCategory(BaseModel):
    name: str
    image_url: Optional[str] = None



class UpdateCategory(BaseModel):
    delivery_status: Optional[str] = None
    status: Optional[str] = None
    amount: float



