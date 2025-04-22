from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from src.config import settings
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from typing import Any, AsyncIterator, AsyncGenerator
import logging

from src.models.user_models import Base
from src.models.wishlist_models import Wishlist, WishlistItem
from src.models.cart_models import Cart, CartItem
from src.models.payment_models import Payment
from src.models.shipping_models import Shipping
from src.models.notification_models import Notification
from src.models.product_models import Product, ProductImage
from src.models.category_models import ProductCategory
from src.errors.database_errors import DatabaseConnectionError, DatabaseSessionError


logger = logging.getLogger(__name__)


class DatabaseSessionManager:
    def __init__(self, database_url: str, engine_settings: dict):
        self._async_engine = None
        self._session_maker = None
        self.database_url = database_url
        self.engine_settings = engine_settings
        self.is_connected = False
        
        # Initialize the database engine and session maker without testing connection
        self._initialize_engine()
        
        
    def _initialize_engine(self) -> None:
        """Initialize the engine and session maker."""
        try:
            self._async_engine = create_async_engine(url=self.database_url,
                                                **self.engine_settings)
            self._session_maker = sessionmaker(autocommit=False, #If True, each transaction will be automatically committed.
                                            autoflush=False, #If True, the session will automatically flush changes to the database. 
                                            bind=self._async_engine,
                                            class_=AsyncSession,
                                            expire_on_commit=False #If True, the session will expire all instances after commit. 
                                            )
            logger.info("Database engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database engine: {str(e)}")
            self._async_engine = None
            self._session_maker = None

        
    async def init_db(self) -> bool:
        """Initialize the database, creating all tables."""
        if self._async_engine is None:
            raise DatabaseConnectionError("Database engine is not initialized.")
            #return False
        
        try:
            # Create all tables in the database
            async with self._async_engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            logger.info("Database tables initialized successfully")
            self.is_connected = True
            return True
        except (DBAPIError, SQLAlchemyError, OSError) as e:
            logger.error(f"Database connection error: {str(e)}")
            raise DatabaseConnectionError(f"Database connection error: {str(e)}")
            #return False
        except Exception as e:
            logger.error(f"Unexpected error during database initialization: {str(e)}")
            raise DatabaseConnectionError(f"Unexpected error during database initialization: {str(e)}")
            #return False
        
    async def close(self) -> None:
        """Close the database engine and session maker."""
        if self._async_engine is None:
            raise DatabaseConnectionError("Database engine is not initialized.")
        await self._async_engine.dispose()
        
        self.is_connected = False
        self._async_engine = None
        self._session_maker = None
        

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[AsyncConnection]:
        """Provide a transactional scope around a series of operations.
         # Check if the engine is initialized
         # If not, raise an error
         # If yes, create a connection and yield it
         # Handle exceptions and rollback if necessary
        """
        if self.is_connected:
            logger.info("Already connected to the database.")
            raise DatabaseConnectionError("Already connected to the database.")
        if self._async_engine is None:
            raise DatabaseConnectionError("Database engine is not initialized.")
        
        if not self.is_connected:
            raise DatabaseConnectionError("Database is not connected.")
        
        if self._session_maker is None:
            raise DatabaseSessionError("Session maker is not initialized.")
        
        async with self._async_engine.begin() as connection:
            try:
                yield connection
            except DBAPIError as e:
                await connection.rollback()
                self.is_connected = False
                logger.error(f"Database error: {str(e)}")
                raise DatabaseConnectionError(f"Database error: {str(e)}")
            except Exception as e: 
                await connection.rollback()
                self.is_connected = False
                logger.error(f"Database connection error: {str(e)}")
                raise DatabaseConnectionError(f"Database connection error: {str(e)}")


    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Provide a transactional scope around a series of operations.
         # Check if the session maker is initialized
         # If not, raise an error
         # If yes, create a session and yield it
         # Handle exceptions and rollback if necessary
        """
        if self._session_maker is None:
            raise DatabaseSessionError("Session maker is not initialized.")
        
        session = self._session_maker()
        try:
            yield session
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"SQLAlchemy error: {str(e)}")
            raise DatabaseSessionError(f"Database session error: {str(e)}")
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {str(e)}")
            raise DatabaseSessionError(f"Database session error: {str(e)}")
        finally:
            await session.close()
        

database_session_manager = DatabaseSessionManager(settings.DATABASE_URL, 
                                                engine_settings={"echo": False,  # Set to True in develpment for logging SQL queries
                                                                "pool_pre_ping": True,  # If True, the connection pool will check for stale connections and refresh them.
                                                                "pool_size": 100, # The maximum number of database connections to pool
                                                                "max_overflow": 0, #The maximum number of connections to allow in the connection pool above pool_size. It's set to 0, meaning no overflow connections are allowed.
                                                                })

    
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional scope around for each series (request) of operations with database."""
    async with database_session_manager.session() as session:
        yield session