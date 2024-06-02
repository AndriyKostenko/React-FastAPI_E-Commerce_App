from datetime import datetime
from typing import Optional, List, Dict

from pydantic import BaseModel, ConfigDict
from pydantic.fields import Field


class ImageType(BaseModel):
    color: str
    color_code: str
    image: str

    model_config = ConfigDict(from_attributes=True)

class CreateProduct(BaseModel):
    name: str
    description: str
    category: str
    brand: str
    images: List[ImageType]
    quantity: int
    price: float
    in_stock: bool

    model_config = ConfigDict(from_attributes=True)


class UserInfoProductRating(BaseModel):
    name: str
    image: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class Review(BaseModel):
    id: str
    user_id: str
    product_id: str
    rating: int
    comment: str
    created_date: str
    user: UserInfoProductRating

    model_config = ConfigDict(from_attributes=True)


class Image(BaseModel):
    color: str
    color_code: str
    image: str

    model_config = ConfigDict(from_attributes=True)


class ProductSchema(BaseModel):
    id: int
    name: str
    description: str
    price: float
    brand: str
    category: str
    in_stock: bool
    images: List[Image]
    reviews: List[Review]

    model_config = ConfigDict(from_attributes=True)


class GetAllProducts(BaseModel):
    products: List[ProductSchema]
