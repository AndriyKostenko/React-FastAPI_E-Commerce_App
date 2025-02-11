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
    quantity: PositiveInt
    price: PositiveFloat
    in_stock: Optional[bool] = None
    date_created: Optional[str] = None


class CategoryProps(BaseModel):
    id: str
    name: str
    image_url: str
    date_created: str
    date_updated: str

class ProductSchema(BaseModel):
    id: str
    name: str
    description: str
    price: float
    quantity: int
    brand: str
    category: CategoryProps
    in_stock: bool
    date_created: str
    selected_image: CartImages
    images: List[CartImages]
    reviews: List[Review]

class GetAllProducts(BaseModel):
    products: List[ProductSchema]


class ProductParams(BaseModel):
    category: Optional[str] = None
    searchTerm: Optional[str] = None
