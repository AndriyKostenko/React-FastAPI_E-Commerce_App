from typing import Protocol
from uuid import UUID

from database_layer.generated_design_repository import GeneratedDesignRepository
from infrastructure.managers.database_session_manager import DatabaseSessionManager


class GeneratedDesignLog(Protocol):
    """Notes each stored design and who made it, so retention can find it later."""

    async def record(self, key: str, user_id: UUID | None) -> None:
        ...


class DatabaseGeneratedDesignLog:
    """A GeneratedDesignLog kept in the product database, in a transaction of its own."""

    def __init__(self, database: DatabaseSessionManager) -> None:
        self._database = database

    async def record(self, key: str, user_id: UUID | None) -> None:
        async with self._database.transaction() as session:
            await GeneratedDesignRepository(session).record(key, user_id)
