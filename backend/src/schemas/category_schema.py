from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict
from pydantic.fields import Field




class CreateCategory(BaseModel):
    name: str
    image_url: Optional[str] = None



class UpdateCategory(BaseModel):
    delivery_status: Optional[str] = None
    status: Optional[str] = None
    amount: float



