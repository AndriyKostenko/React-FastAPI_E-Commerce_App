"""Authentication claims shared by the token issuer and API gateway."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class AuthMethod(StrEnum):
    """How a session was signed in: the token's ``amr`` claim (RFC 8176 style)."""

    PASSWORD = "pwd"
    GOOGLE = "google"
    PASSKEY = "webauthn"


class TokenClaims(BaseModel):
    """Validated JWT claims exposed to services after gateway authentication."""

    email: EmailStr
    id: UUID
    role: str | None
    purpose: str | None = None
    token_version: int | None = None
    # Carried from sign-in through every refresh, so an admin session can be
    # told apart from one that only ever presented a password.
    amr: list[AuthMethod] = Field(default_factory=list)

    def signed_in_with_passkey(self) -> bool:
        return AuthMethod.PASSKEY in self.amr
