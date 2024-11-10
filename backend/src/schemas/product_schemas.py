from datetime import datetime
from typing import Optional, List, Dict

from pydantic import BaseModel, ConfigDict
from src.schemas.review_schemas import Review


class ImageType(BaseModel):
    color: str
    color_code: str
    image: str

class CartImages(BaseModel):
    image_color: str
    id: str
    product_id: str
    image_url:str
    image_color_code: str


class CreateProduct(BaseModel):
    name: str
    description: str
    category_id: str
    brand: str
    images: List[ImageType]
    quantity: int
    price: float
    in_stock: Optional[bool] = None
    date_created: Optional[datetime] = None


class CategoryProps(BaseModel):
    id: str
    name: str

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
