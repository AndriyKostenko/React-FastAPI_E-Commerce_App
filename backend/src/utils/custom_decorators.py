from functools import wraps
 
from sqlalchemy.exc import (IntegrityError, 
                            OperationalError, 
                            SQLAlchemyError, 
                            TimeoutError, 
                            StatementError,
                            ProgrammingError,
                            DBAPIError)
from src.errors.database_errors import (
    DatabaseError,
    DatabaseConnectionError,
    DatabaseIntegrityError,
    DatabaseOperationError,
    DatabaseTimeoutError,
    DatabaseTransactionError,
    DatabaseProgrammingError,
    DatabaseTableNotFoundError
)
import logging

logger = logging.getLogger(__name__)

def handle_db_errors(func):
    """
    Decorator to handle database-related errors.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except IntegrityError as e:
            logger.error(f"Database integrity error in {func.__name__}: {str(e)}")
            raise DatabaseIntegrityError(f"Database integrity error: {str(e)}")
        except OperationalError as e:
            logger.error(f"Database connection error in {func.__name__}: {str(e)}")
            raise DatabaseConnectionError(f"Database connection error: {str(e)}")
        # looks likecatching only this type of error in regards to others, even if others were in place as well
        except SQLAlchemyError as e:
            logger.error(f"Database error in {func.__name__}: {str(e)}")
            raise DatabaseOperationError(f"Database operation failed: {str(e)}")
        except TimeoutError as e:
            logger.error(f"Database timeout error in {func.__name__}: {str(e)}")
            raise DatabaseTimeoutError(f"Database operation timed out: {str(e)}")
        except StatementError as e:
            logger.error(f"Database statement error in {func.__name__}: {str(e)}")
            raise DatabaseError(f"Database statement error: {str(e)}")
        except ProgrammingError as e:
            raise DatabaseProgrammingError(f"Database programming error: {str(e)}")
        except DBAPIError as e:
            # Check if the underlying error is UndefinedTableError
            logger.error(f"Database API error in {func.__name__}: {str(e)}")
            if "UndefinedTableError" in str(e.__cause__):
                table_name = str(e.__cause__).split('"')[1]  # Extract table name from error
                raise DatabaseTableNotFoundError(table_name)
            raise DatabaseProgrammingError(f"Database programming error: {str(e)}")
            
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