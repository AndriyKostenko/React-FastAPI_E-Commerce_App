from datetime import datetime
from typing import Optional, List, Dict
from uuid import UUID
from pydantic import BaseModel, PositiveInt, PositiveFloat, Field

from schemas.review_schemas import ReviewSchema
from schemas.category_schema import CategorySchema

class ImageType(BaseModel):
    color: str = Field(..., min_length=3, max_length=50, description="Image color must be between 3 and 50 characters", example="Black")
    color_code: str = Field(..., min_length=3, max_length=50, description="Image color code must be between 3 and 50 characters" , example="#000000")
    image: str = Field(..., min_length=3, max_length=100, description="Image URL must be between 3 and 500 characters", example="https://example.com/image.jpg")

class CartImages(BaseModel):
    product_id: UUID = Field(..., description="Product ID is required", example="123e4567-e89b-12d3-a456-426614174000", min_length=10, max_length=100)
    image_url: str = Field(..., min_length=3, max_length=100, description="Image URL must be between 3 and 500 characters", example="https://example.com/image.jpg")
    image_color_code: str = Field(..., min_length=3, max_length=50, description="Image color code must be between 3 and 50 characters" , example="#000000")
    id: UUID = Field(..., description="Image ID is required", example="123e4567-e89b-12d3-a456-426614174000", min_length=10, max_length=100)
    image_color: str = Field(..., min_length=3, max_length=50, description="Image color must be between 3 and 50 characters", example="Black")


class CreateProduct(BaseModel):
    name: str = Field(..., min_length=3, max_length=50, description="Product name must be between 3 and 50 characters")
    description: str = Field(..., min_length=10, max_length=500, description="Product description must be between 10 and 500 characters")
    category_id: str =  Field(..., description="Category ID is required")
    brand: str = Field(..., min_length=3, max_length=50, description="Brand name must be between 3 and 50 characters")
    images: List[ImageType]
    quantity: int = PositiveInt
    price: float = PositiveFloat
    in_stock: Optional[bool] = None




class ProductSchema(BaseModel):
    id: UUID = Field(..., description="Product ID is required", example="123e4567-e89b-12d3-a456-426614174000", min_length=10, max_length=100)
    name: str = Field(..., description="Product name is required", examples=["Nike Air Max", "Adidas Superstar"], min_length=3, max_length=50)
    description: str = Field(..., description="Product description is required", examples=["The best shoes in the market", "The most comfortable shoes"], min_length=10, max_length=500)
    price: float = PositiveFloat
    quantity: int = PositiveInt
    brand: str = Field(..., description="Product brand is required", example="Nike", min_length=3, max_length=50)
    category: CategorySchema = Field(..., description="Category schema is required")
    date_created: datetime
    date_updated: Optional[datetime] = None
    in_stock: bool = Field(..., description="Product in_stock status is required", example=True)
    selected_image: Optional[CartImages] = None
    images: List[CartImages] 
    reviews: Optional[List[ReviewSchema]] = None
    
class CreatedProduct(BaseModel):
    id: UUID = Field(..., description="Product ID is required", example="123e4567-e89b-12d3-a456-426614174000", min_length=10, max_length=100)
    category_id: str = Field(..., description="Category ID is required", example="123e4567-e89b-12d3-a456-426614174000", min_length=10)
    quantity: int = PositiveInt
    in_stock: bool = Field(..., description="Product in_stock status is required", example=True)
    date_updated: Optional[datetime] = None
    name: str = Field(..., description="Product name is required", examples=["Nike Air Max", "Adidas Superstar"], min_length=3, max_length=50)
    description: str = Field(..., description="Product description is required", examples=["The best shoes in the market", "The most comfortable shoes"], min_length=10, max_length=500)
    brand: str = Field(..., description="Product brand is required", example="Nike", min_length=3, max_length=50)
    price: float = PositiveFloat
    date_created: datetime
    

class ProductParams(BaseModel):
    category: Optional[str] = Field(None, description="Category name is required", example="Shoes", min_length=3, max_length=50)
    searchTerm: Optional[str] = Field(None, description="Search term is required", example="Nike", min_length=3, max_length=50)
