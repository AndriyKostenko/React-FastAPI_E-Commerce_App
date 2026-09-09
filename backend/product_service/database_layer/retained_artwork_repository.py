from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.retained_artwork_models import RetainedArtwork
from shared.database_layer.database_layer import BaseRepository


class RetainedArtworkRepository(BaseRepository[RetainedArtwork]):
    """Reads and writes the holds that protect ordered artwork from cleanup."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, RetainedArtwork)

    async def get_active(self, order_id: UUID, artwork_key: str) -> RetainedArtwork | None:
        result = await self.session.execute(
            select(RetainedArtwork).where(
                RetainedArtwork.order_id == order_id,
                RetainedArtwork.artwork_key == artwork_key,
                RetainedArtwork.released_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_order(self, order_id: UUID) -> list[RetainedArtwork]:
        result = await self.session.execute(
            select(RetainedArtwork).where(
                RetainedArtwork.order_id == order_id,
                RetainedArtwork.released_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def is_key_retained(self, artwork_key: str) -> bool:
        """True while any order still holds this object.

        A cleanup job asks this before deleting an object: one live hold from
        any order is enough to keep the print file.
        """
        result = await self.session.execute(
            select(RetainedArtwork.id)
            .where(
                RetainedArtwork.artwork_key == artwork_key,
                RetainedArtwork.released_at.is_(None),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
