from logging import Logger
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import MetaData, URL, text
from sqlalchemy.pool import NullPool

from .database_session_manager import DatabaseSessionManager

class TestDatabaseSessionManager(DatabaseSessionManager):
    """
    DatabaseSessionManager pre-configured for the test database.

    Always uses NullPool (no connection reuse between tests) and disables echo.
    Adds truncate_all_tables() for fast between-test isolation.
    """
    def __init__(self, database_url: str | URL, logger: Logger) -> None:
        # Bypass PoolSettingsCalculator — tests always use NullPool.
        self.database_url = database_url
        self.logger = logger
        self.async_engine = None
        self.async_session = None
        self.engine_settings = {"echo": False, "pool_pre_ping": True, "poolclass": NullPool}
        self._initialize_engine()

    # Databases whose schema this test process has already rebuilt.
    _rebuilt: set[str] = set()

    async def init_db(self, metadata: MetaData) -> None:
        """
        On the first call per test process, drop and recreate the schema from
        the models; afterwards, just ensure the tables exist.

        create_all never alters an existing table, so a test database created
        before a model change kept the old columns — tests then ran against a
        schema production does not have (or failed on a missing column).
        """
        key = str(self.database_url)
        if key not in self._rebuilt:
            if self.async_engine is None:
                raise RuntimeError("Database engine is not initialized.")
            async with self.async_engine.begin() as connection:
                await connection.run_sync(metadata.drop_all)
            TestDatabaseSessionManager._rebuilt.add(key)
        await super().init_db(metadata)

    async def truncate_all_tables(self, metadata: MetaData) -> None:
        """
        Delete all rows from every mapped table and restart identity sequences.

        Uses PostgreSQL TRUNCATE … RESTART IDENTITY CASCADE so that:
            - auto-increment PKs reset to 1 (deterministic test IDs)
            - FK-referencing tables are cleared automatically (CASCADE)
        """
        table_names = ", ".join(
            t.name for t in reversed(metadata.sorted_tables)
        )
        if not table_names:
            return
        async with self.async_engine.begin() as conn:
            _ = await conn.execute(
                text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE")
            )
        self.logger.info(f"Truncated test tables: {table_names}")

    async def recreate_schema(self, metadata: MetaData) -> None:
        """Drop and recreate service-owned tables in the configured test database."""
        if self.async_engine is None:
            raise RuntimeError("Test database engine is not initialized")
        async with self.async_engine.begin() as connection:
            await connection.run_sync(metadata.drop_all)
            await connection.run_sync(metadata.create_all)
        self.logger.info("Recreated test database schema from current metadata")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Yield a transactional AsyncSession for dependency override use."""
        async with self.transaction() as session:
            yield session
