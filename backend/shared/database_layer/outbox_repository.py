from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone

from shared.database_layer.database_layer import BaseRepository
from shared.database_layer.repository_mixins import LockableRepositoryMixin


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
