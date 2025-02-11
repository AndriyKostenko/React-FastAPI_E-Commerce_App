from datetime import datetime
from typing import Optional, List, Dict

from pydantic import BaseModel, PositiveInt, PositiveFloat, Field
from src.schemas.review_schemas import Review


class ImageType(BaseModel):
    color: str
    color_code: str
    image: str

class CartImages(BaseModel):
    product_id: str
    image_url: str
    image_color_code: str
    id: str
    image_color: str


class CreateProduct(BaseModel):
    name: str = Field(..., min_length=3, max_length=50, description="Product name must be between 3 and 50 characters")
    description: str = Field(..., min_length=10, max_length=500, description="Product description must be between 10 and 500 characters")
    category_id: str =  Field(..., description="Category ID is required")
    brand: str = Field(..., min_length=3, max_length=50, description="Brand name must be between 3 and 50 characters")
    images: List[ImageType]
    quantity: int = PositiveInt
    price: float = PositiveFloat
    in_stock: Optional[bool] = None
    date_created: Optional[str] = None


class CategoryProps(BaseModel):
    id: str
    name: str
    image_url: str
    date_created: datetime
    date_updated: Optional[datetime] = None

class ProductSchema(BaseModel):
    id: str
    name: str
    description: str
    price: float
    quantity: int
    brand: str
    category: Optional[CategoryProps] = None
    date_created: datetime
    date_updated: Optional[datetime] = None
    in_stock: bool
    selected_image: Optional[CartImages] = None
    images: List[CartImages] 
    reviews: List[Review]
    
class CreatedProduct(BaseModel):
    id: str
    category_id: str
    quantity: int
    in_stock: bool
    date_updated: Optional[str] = None
    name: str
    description: str
    brand: str
    price: float
    date_created: datetime
    

class ProductParams(BaseModel):
    category: Optional[str] = None
    searchTerm: Optional[str] = None
