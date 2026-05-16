from logging import Logger
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import URL, text
from sqlalchemy.pool import NullPool

from shared.models.models_base_class import Base
from .database_session_manager import DatabaseSessionManager

class TestDatabaseSessionManager(DatabaseSessionManager):
    """
    DatabaseSessionManager pre-configured for the test database.

    Adds truncate_all_tables() for fast between-test isolation:
    all rows are deleted in reverse dependency order so FK constraints
    are never violated, and sequences are reset to 1.
    """
    def __init__(self, database_url: str | URL, engine_settings: dict[str, str | int | type[NullPool]], logger: Logger) -> None:
        super().__init__(database_url, engine_settings, logger)

    async def truncate_all_tables(self) -> None:
        """
        Delete all rows from every mapped table and restart identity sequences.

        Uses PostgreSQL TRUNCATE … RESTART IDENTITY CASCADE so that:
            - auto-increment PKs reset to 1 (deterministic test IDs)
            - FK-referencing tables are cleared automatically (CASCADE)
        """
        table_names = ", ".join(
            t.name for t in reversed(Base.metadata.sorted_tables)
        )
        if not table_names:
            return
        async with self.async_engine.begin() as conn:
            _ = await conn.execute(
                text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE")
            )
        self.logger.info(f"Truncated test tables: {table_names}")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Yield a transactional AsyncSession for dependency override use."""
        async with self.transaction() as session:
            yield session
