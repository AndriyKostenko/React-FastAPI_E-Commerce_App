from typing import Optional
from src.schemas.user_schemas import UserInfo

from pydantic import BaseModel



class CreateProductReview(BaseModel):
    product_id: str
    comment: Optional[str] = None
    rating: Optional[float] = None
    user_id: str


class Review(BaseModel):
    id: str
    user_id: str
    product_id: str
    rating: int
    comment: str
    date_created: str
    date_updated: Optional[str] = None
    user: UserInfo