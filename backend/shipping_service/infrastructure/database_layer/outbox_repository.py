from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone

from infrastructure.database_layer.database_layer import BaseRepository
from infrastructure.database_layer.repository_mixins import LockableRepositoryMixin


class OutboxRepository(BaseRepository[DeclarativeBase], LockableRepositoryMixin[DeclarativeBase]):
    """
    This class extends BaseRepository to provide specific methods
    for managing outbox events in the database.
    """
    def __init__(self, session: AsyncSession, model: type[DeclarativeBase]):
        super().__init__(session, model)

    async def get_pending_with_lock(self, limit: int = 50) -> list[DeclarativeBase]:
        query = (
            select(self.model)
            .where(
                self.model.processed.is_(False),
                or_(self.model.next_retry_at.is_(None), self.model.next_retry_at <= datetime.now(timezone.utc)),
            )
            .order_by(self.model.date_created)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete_processed_before(self, cutoff: datetime, limit: int) -> int:
        """Delete up to ``limit`` events published before ``cutoff``, oldest first; how many went."""
        oldest = (
            select(self.model.id)
            .where(self.model.processed.is_(True), self.model.processed_at < cutoff)
            .order_by(self.model.processed_at)
            .limit(limit)
        )
        result = await self.session.execute(delete(self.model).where(self.model.id.in_(oldest)))
        return result.rowcount or 0
