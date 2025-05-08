from pydantic import BaseModel, EmailStr
from typing import List, Dict, Any

class EmailSchema(BaseModel):
    email: EmailStr
    body: dict

