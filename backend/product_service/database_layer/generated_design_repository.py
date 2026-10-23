from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.generated_design_models import GeneratedDesign
from models.retained_artwork_models import RetainedArtwork
from infrastructure.database_layer.database_layer import BaseRepository


class GeneratedDesignRepository(BaseRepository[GeneratedDesign]):
    """The stored designs and who made them; which of them no order holds."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, GeneratedDesign)

    async def record(self, key: str, user_id: UUID | None) -> None:
        # A redelivered job that stored the same key again changes nothing.
        await self.session.execute(
            insert(GeneratedDesign).values(key=key, user_id=user_id).on_conflict_do_nothing(index_elements=["key"])
        )

    async def unordered(
        self, limit: int, made_before: datetime | None = None, user_id: UUID | None = None
    ) -> list[GeneratedDesign]:
        """Designs no live order hold protects, oldest first, narrowed by age and/or owner."""
        held = exists().where(
            RetainedArtwork.artwork_key == GeneratedDesign.key,
            RetainedArtwork.released_at.is_(None),
        )
        query = select(GeneratedDesign).where(~held)
        if made_before is not None:
            query = query.where(GeneratedDesign.date_created < made_before)
        if user_id is not None:
            query = query.where(GeneratedDesign.user_id == user_id)
        result = await self.session.execute(query.order_by(GeneratedDesign.date_created).limit(limit))
        return list(result.scalars().all())

    async def forget(self, keys: Sequence[str]) -> None:
        await self.session.execute(delete(GeneratedDesign).where(GeneratedDesign.key.in_(list(keys))))
