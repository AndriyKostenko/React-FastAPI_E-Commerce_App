from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict
from pydantic.fields import Field


class CreateProduct(BaseModel):
    id: str
    name: str
    description: str
    category: str
    brand: str
    image_url: str
    quantity: int
    price: float
