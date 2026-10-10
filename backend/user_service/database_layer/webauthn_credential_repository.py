from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.webauthn_credential_models import WebAuthnCredential
from shared.database_layer.database_layer import BaseRepository


class WebAuthnCredentialRepository(BaseRepository[WebAuthnCredential]):
    """The passkeys each admin has registered."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, WebAuthnCredential)

    async def list_for_user(self, user_id: UUID) -> list[WebAuthnCredential]:
        result = await self.session.execute(
            select(WebAuthnCredential)
            .where(WebAuthnCredential.user_id == user_id)
            .order_by(WebAuthnCredential.date_created)
        )
        return list(result.scalars().all())

    async def lock_for_sign_in(self, user_id: UUID, credential_id: bytes) -> WebAuthnCredential | None:
        """The user's credential with this id, row-locked until the transaction ends.

        Locked because the stored sign count is compared and then raised: two
        sign-ins with the same passkey must not both pass against the old count.
        """
        result = await self.session.execute(
            select(WebAuthnCredential)
            .where(
                WebAuthnCredential.user_id == user_id,
                WebAuthnCredential.credential_id == credential_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def record_use(self, credential: WebAuthnCredential, sign_count: int, used_at: datetime) -> None:
        credential.sign_count = sign_count
        credential.last_used_at = used_at
        await self.session.flush()

    async def delete_for_user(self, user_id: UUID, credential_row_id: UUID) -> bool:
        credential = await self.session.get(WebAuthnCredential, credential_row_id)
        if credential is None or credential.user_id != user_id:
            return False
        await self.delete(credential)
        return True
