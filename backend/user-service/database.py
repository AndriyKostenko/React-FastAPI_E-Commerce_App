from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any

from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine

from utils.logger_config import setup_logger
from models import Base
from errors import DatabaseConnectionError, DatabaseSessionError
from config import get_settings

logger = setup_logger(__name__)
settings = get_settings()


class DatabaseSessionManager:
    def __init__(self, database_url: str, engine_settings: Dict[str, int]) -> None:
        self.async_engine = None
        self.async_session = None
        self.database_url = database_url
        self.engine_settings = engine_settings
        
        # Initializing the database engine and session maker 
        self._initialize_engine()
        
        
    def _initialize_engine(self) -> None:
        """Initialize the engine and session maker."""
        try:
            self.async_engine: AsyncEngine = create_async_engine(url=self.database_url,
                                                **self.engine_settings)
            self.async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
                                            autocommit=False, #If True, each transaction will be automatically committed.
                                            autoflush=False, #If True, the session will automatically flush changes to the database. 
                                            bind=self.async_engine,
                                            class_=AsyncSession,
                                            expire_on_commit=False #If True, the session will expire all instances after commit. 
                                            )
            logger.info("Database engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database engine: {str(e)}")
            self.async_engine = None
            self.async_session = None

        
    async def init_db(self) -> None:
        """Initialize the database and create all tables."""
        if self.async_engine is None:
            logger.error("Database engine is not initialized.")
            raise DatabaseConnectionError("Database engine is not initialized.")
        
        try:
            async with self.async_engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            logger.info("Database tables initialized successfully")
        except Exception as e:
            logger.error(f"Unexpected error during database initialization: {str(e)}")
            raise DatabaseConnectionError(f"Unexpected error during database initialization: {str(e)}")


    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession]:
        """Provide a transactional scope for ORM operations.
            - low level session manager
            - creates the actual db session
            - handles transactions management
            - yields the session for use in the context
        """
        if self.async_session is None:
            logger.error("Session maker is not initialized.")
            raise DatabaseSessionError("Session maker is not initialized.")
        
        async with self.async_session() as session:
            try:
                yield session
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"Database transaction error: {str(e)}")
                raise DatabaseSessionError(f"Database transaction failed: {str(e)}") from e
                
            
            
    async def close(self) -> None:
        """Dispose the database engine."""
        if self.async_engine is not None:
            await self.async_engine.dispose()
            logger.warning("Database engine disposed.")
        self.async_engine = None
        self.async_session = None
        



database_session_manager = DatabaseSessionManager(
    database_url=settings.DATABASE_URL, 
    engine_settings={"echo": True,  # Set to True in develpment for logging SQL queries
                     "pool_pre_ping": True,  # If True, the connection pool will check for stale connections and refresh them.
                     "pool_size": 100, # The maximum number of database connections to pool
                     "max_overflow": 0, #The maximum number of connections to allow in the connection pool above pool_size. It's set to 0, meaning no overflow connections are allowed.
                    })


