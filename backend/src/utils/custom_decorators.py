from functools import wraps
from sqlalchemy import exc
 
from sqlalchemy.exc import (SQLAlchemyError, 
                            DBAPIError,
                            InterfaceError as SQLAlchemyInterfaceError)

from asyncpg.exceptions._base import InterfaceError as AsyncPGInterfaceError
from src.errors.database_errors import (
    DatabaseConnectionError,
    DatabaseOperationError,
    DatabaseTransactionError,

)
import logging

logger = logging.getLogger(__name__)

def handle_db_errors(func):
    """
    Decorator to handle SQLAlchemy database-related errors.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        # looks likecatching only this type of error in regards to others SQLAlchemy errors, even if others were in place as well
        except SQLAlchemyError as e:
            logger.error(f"Database error in {func.__name__}: {str(e)}")
            raise DatabaseOperationError(f"Database operation failed due to SQLAlchemy error: {str(e)}")
        
        #TODO: cannot catch database off errors, when poastgress doesnt work....
        except (AsyncPGInterfaceError, SQLAlchemyInterfaceError, ConnectionRefusedError, exc.DBAPIError, DBAPIError) as e:
            logger.error(f"Database connection lost in {func.__name__}: {str(e)}")
            raise DatabaseConnectionError(
                "Database connection is closed. The server might be down or restarting."
            )
            
    return wrapper


def handle_db_transaction_rollbacks(func):
    """Decorator to handle database transaction rollbacks.
    This decorator ensures that if an exception occurs during the execution of a function,
    the database transaction is rolled back.
    """
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            result = await func(self, *args, **kwargs)
            await self.session.commit()
            await self.session.refresh(result)
            logger.info(f"Transaction committed successfully in: {func.__name__}")
            return result
        except Exception as e: # for now catching all exceptions...later we can be more specific
            logger.error(f"Transaction failed in {func.__name__}: {e}")
            await self.session.rollback()
            raise DatabaseTransactionError(f"Transaction failed: {e}")
        finally:
            await self.session.close()
    return wrapper