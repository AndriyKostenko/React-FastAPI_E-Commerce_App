from uuid import UUID

from pydantic import BaseModel,  EmailStr


class CurrentUserInfo(BaseModel):
    email: EmailStr
    id: UUID
    role: str | None