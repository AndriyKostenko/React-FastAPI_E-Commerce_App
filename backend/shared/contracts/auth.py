"""Authentication claims shared by the token issuer and API gateway."""

from uuid import UUID

from pydantic import BaseModel, EmailStr


class TokenClaims(BaseModel):
    """Validated JWT claims exposed to services after gateway authentication."""

    email: EmailStr
    id: UUID
    role: str | None
    purpose: str | None = None
    token_version: int | None = None
