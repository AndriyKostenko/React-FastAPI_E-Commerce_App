from contextlib import asynccontextmanager
from logging import Logger
from typing import AsyncGenerator, Dict

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine # type: ignore

from shared.models.models_base_class import Base # type: ignore
from shared.base_exceptions import BaseAPIException, DatabaseConnectionError, DatabaseSessionError # type: ignore




class DatabaseSessionManager:
    """
    Manages database sessions and connections for the application.
    - Initializes the database engine and session maker.
    - Provides a method to initialize the database and create all tables.
    - Provides a context manager for transactional scope for ORM operations.
    - Handles connection pooling and session management.
    - Provides a method to close the database connection.
    - Handles errors related to database connection and session management.
    - Uses async context manager for session management.
    - Uses SQLAlchemy's async engine and sessionmaker for asynchronous operations.
    - Uses a logger for logging database operations and errors.
    """
    def __init__(self, database_url: str, engine_settings: Dict[str, int], logger: Logger) -> None:
        self.async_engine: AsyncEngine | None = None
        self.async_session: async_sessionmaker[AsyncSession] | None = None
        self.database_url: str = database_url
        self.engine_settings = engine_settings
        self.logger: Logger = logger

        # Initializing the database engine and session maker
        self._initialize_engine()


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
                    expire_on_commit=False #If True, the session will expire all instances after commit.
            )
            self.logger.info("Database engine initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize database engine: {str(e)}")
            self.async_engine = None
            self.async_session = None


    async def init_db(self) -> None:
        """Initialize the database and create all tables."""
        if self.async_engine is None:
            self.logger.error("Database engine is not initialized.")
            raise DatabaseConnectionError("Database engine is not initialized.")

        try:
            async with self.async_engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
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
                # Expected business logic errors (4xx) - rollbacl silently
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
