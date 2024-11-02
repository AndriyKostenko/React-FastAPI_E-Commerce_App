from datetime import datetime
from typing import Optional, List, Dict

from pydantic import BaseModel, ConfigDict
from pydantic.fields import Field


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


class CreateProductReview(BaseModel):
    product_id: str
    comment: str
    rating: float
    user_id: str


class UserInfoProductRating(BaseModel):
    name: str
    image: Optional[str] = None


class Review(BaseModel):
    id: str
    user_id: str
    product_id: str
    rating: int
    comment: str
    created_date: str
    user: UserInfoProductRating

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
