from datetime import datetime
from typing import Optional, List, Dict

from pydantic import BaseModel, ConfigDict
from pydantic.fields import Field


class ImageType(BaseModel):
    color: str
    color_code: str
    image: str

<<<<<<< HEAD
=======

>>>>>>> 0ed6875cfb190c545220d7e49a5687ef2f564754

class CreateProduct(BaseModel):
    name: str
    description: str
    category: str
    brand: str
    images: List[ImageType]
    quantity: int
    price: float
    in_stock: bool


<<<<<<< HEAD
class CreateProductReview(BaseModel):
    product_id: str
    comment: str
    rating: float
    user_id: int
=======
>>>>>>> 0ed6875cfb190c545220d7e49a5687ef2f564754


class UserInfoProductRating(BaseModel):
    name: str
    image: Optional[str] = None

<<<<<<< HEAD
=======

>>>>>>> 0ed6875cfb190c545220d7e49a5687ef2f564754

class Review(BaseModel):
    id: str
    user_id: str
    product_id: str
    rating: int
    comment: str
    created_date: str
    user: UserInfoProductRating

<<<<<<< HEAD
=======


>>>>>>> 0ed6875cfb190c545220d7e49a5687ef2f564754

class Image(BaseModel):
    color: str
    color_code: str
    image: str

<<<<<<< HEAD
=======


>>>>>>> 0ed6875cfb190c545220d7e49a5687ef2f564754

class ProductSchema(BaseModel):
    id: str
    name: str
    description: str
    price: float
    brand: str
    category: str
    in_stock: bool
    images: List[Image]
    reviews: List[Review]

<<<<<<< HEAD
=======


>>>>>>> 0ed6875cfb190c545220d7e49a5687ef2f564754

class GetAllProducts(BaseModel):
    products: List[ProductSchema]


class ProductParams(BaseModel):
    category: Optional[str] = None
    searchTerm: Optional[str] = None