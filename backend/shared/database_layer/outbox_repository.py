from sqlalchemy.ext.asyncio import AsyncSession

from shared.database_layer.database_layer import BaseRepository
from shared.database_layer.repository_mixins import LockableRepositoryMixin
from shared.models.outbox_events import OutboxEvent


class OutboxRepository(BaseRepository[OutboxEvent], LockableRepositoryMixin[OutboxEvent]):
    """
    This class extends BaseRepository to provide specific methods
    for managing outbox events in the database.
    """
    def __init__(self, session: AsyncSession):
        super().__init__(session, OutboxEvent)
