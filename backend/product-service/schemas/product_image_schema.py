
from uuid import UUID

from fastapi import Form, UploadFile, File
from pydantic import BaseModel, PositiveInt, Field, ConfigDict, HttpUrl



class ProductImageSchema(BaseModel):
    """Schema for product image representation."""
    id: UUID
    product_id: UUID 
    image_url: HttpUrl
    image_color: str 
    image_color_code: str

    model_config = ConfigDict(from_attributes=True)


class ImageType(BaseModel):
    image_color: str
    image_color_code: str
    image_url: str
    # image_url: HttpUrl

    model_config = ConfigDict(from_attributes=True)

