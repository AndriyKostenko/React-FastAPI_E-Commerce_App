from datetime import datetime
from typing import Optional, List, Dict

from pydantic import BaseModel, ConfigDict
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
    name: str
    description: str
    category_id: str
    brand: str
    images: List[ImageType]
    quantity: int
    price: float
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
