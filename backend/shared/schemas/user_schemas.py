from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr
from pydantic.fields import Field

class CurrentUserInfo(BaseModel):
    email: EmailStr
    id: UUID
    role: str | None