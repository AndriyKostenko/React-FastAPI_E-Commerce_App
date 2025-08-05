from curses.ascii import HT
from uuid import UUID

from pydantic import BaseModel, PositiveInt, Field, ConfigDict, HttpUrl



class ProductImageSchema(BaseModel):
    """Schema for product image representation."""
    id: UUID
    product_id: UUID
    image_url: HttpUrl
    image_color: str = Field(..., min_length=3, max_length=20, description="Image color must be between 3 and 50 characters", example="Black")
    image_color_code: str = Field(..., min_length=3, max_length=20, description="Image color code must be between 3 and 50 characters", example="#000000")

    model_config = ConfigDict(from_attributes=True)


class CreateProductImage(BaseModel):
    """Schema for creating a product image."""
    product_id: UUID
    image_url: HttpUrl
    image_color: str = Field(..., min_length=3, max_length=20, description="Image color must be between 3 and 50 characters", example="Black")
    image_color_code: str = Field(..., min_length=3, max_length=20, description="Image color code must be between 3 and 50 characters", example="#000000")

    model_config = ConfigDict(from_attributes=True)


class ImageType(BaseModel):
    image_color: str = Field(..., min_length=3, max_length=20, description="Image color must be between 3 and 50 characters", example="Black")
    image_color_code: str = Field(..., min_length=3, max_length=20, description="Image color code must be between 3 and 50 characters" , example="#000000")
    image_url: HttpUrl

    model_config = ConfigDict(from_attributes=True)

class CartImages(BaseModel):
    product_id: UUID 
    image_url: str
    image_color_code: str = Field(..., min_length=3, max_length=50, description="Image color code must be between 3 and 50 characters" , example="#000000")
    id: UUID 
    image_color: str = Field(..., min_length=3, max_length=50, description="Image color must be between 3 and 50 characters", example="Black")

    model_config = ConfigDict(from_attributes=True)