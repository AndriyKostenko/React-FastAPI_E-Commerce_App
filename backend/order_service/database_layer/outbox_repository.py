from sqlalchemy.ext.asyncio import AsyncSession

from models.outbox_events import OutboxEvent
from shared.database_layer import BaseRepository


class OutboxRepository(BaseRepository[OutboxEvent]):
    """
    This class extends BaseRepository to provide specific methods
    for managing orders in the database.
    """
    def __init__(self, session: AsyncSession):
        super().__init__(session, OutboxEvent)
