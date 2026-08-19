from contextlib import asynccontextmanager
from logging import Logger
from collections.abc import AsyncGenerator
from types import TracebackType
from typing import Self

from sqlalchemy import MetaData, URL
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine

from shared.exceptions.base_exceptions import BaseAPIException, DatabaseConnectionError, DatabaseSessionError
from shared.database_layer.pool_settings import PoolSettingsCalculator


class DatabaseSessionManager:
    """
    Manages database sessions and connections for the application.

    Accepts PostgreSQL capacity figures and delegates pool-size calculation to
    PoolSettingsCalculator — callers never need to instantiate it directly.
    """
    def __init__(
        self,
        database_url: str | URL,
        logger: Logger,
        *,
        echo: bool = False,
        pg_max_connections: int = 100,
        reserved_connections: int = 5,
        num_db_services: int = 5,
        pool_timeout: int = 5,
        pool_recycle: int = 1800,
    ) -> None:
        self.database_url: str | URL = database_url
        self.logger: Logger = logger
        self.async_engine: AsyncEngine | None = None
        self.async_session: async_sessionmaker[AsyncSession] | None = None

        pool = PoolSettingsCalculator(
            pg_max_connections=pg_max_connections,
            reserved_connections=reserved_connections,
            num_db_services=num_db_services,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
        ).calculate()
        self.engine_settings: dict[str ,str|int] = pool.as_dict(echo=echo)

        self._initialize_engine()

    async def __aenter__(self) -> Self:
        """Register this manager with an async resource-owning context."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Dispose the database engine when leaving its owning async context."""
        await self.close()

    def _initialize_engine(self) -> None:
        """Initialize the engine and session maker."""
        try:
            self.async_engine = create_async_engine(url=self.database_url,
                                                     **self.engine_settings)
            self.async_session = async_sessionmaker(
                    autocommit=False, #If True, each transaction will be automatically committed.
                    autoflush=False, #If True, the session will automatically flush changes to the database.
                    bind=self.async_engine,
                    class_=AsyncSession,
                    expire_on_commit=False, #If True, the session will expire all instances after commit.
            )
            self.logger.info("Database engine initialized")
        except Exception as e:
            self.logger.exception("Failed to initialize database engine")
            raise DatabaseConnectionError(
                f"Failed to initialize database engine: {e}"
            ) from e

    async def init_db(self, metadata: MetaData) -> None:
        """Create missing tables from one service's explicitly supplied metadata.

        This is a bootstrap mechanism, not a migration engine: it deliberately
        cannot alter existing columns.  Each caller must pass its own service
        ``Base.metadata`` so schemas never bleed across service boundaries.
        """
        if self.async_engine is None:
            self.logger.error("Database engine is not initialized.")
            raise DatabaseConnectionError("Database engine is not initialized.")
        try:
            async with self.async_engine.begin() as connection:
                await connection.run_sync(metadata.create_all)
            self.logger.info("Database tables initialized successfully")
        except Exception as e:
            self.logger.error(f"Unexpected error during database initialization: {str(e)}")
            raise DatabaseConnectionError(f"Unexpected error during database initialization: {str(e)}")

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncSession, None]:
        if self.async_session is None:
            raise DatabaseSessionError("Session maker is not initialized.")

        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except BaseAPIException as e:
                # Expected business logic errors (4xx) — rollback silently
                await session.rollback()
                self.logger.warning(f"Session rollback due to expected exception: {e.status_code}: {e.detail}")
                raise
            except Exception as e:
                await session.rollback()
                self.logger.exception(f"Session rollback due to exception: {str(e)}")
                raise

    async def close(self) -> None:
        """Dispose the database engine."""
        if self.async_engine is not None:
            await self.async_engine.dispose()
            self.logger.warning("Database engine disposed.")
        self.async_engine = None
        self.async_session = None
