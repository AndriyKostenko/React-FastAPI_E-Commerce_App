from uuid import UUID

from database_layer.design_moderation_refusal_repository import DesignModerationRefusalRepository
from infrastructure.managers.database_session_manager import DatabaseSessionManager
from service_layer.design_moderation import DesignRefusal


class DatabaseDesignRefusalLog:
    """A DesignRefusalLog that keeps each refusal in the product database, in a transaction of its own."""

    def __init__(self, database: DatabaseSessionManager) -> None:
        self._database = database

    async def record(self, user_id: UUID | None, prompt: str, style: str, refusal: DesignRefusal) -> None:
        async with self._database.transaction() as session:
            await DesignModerationRefusalRepository(session).record(user_id, prompt, style, refusal)
