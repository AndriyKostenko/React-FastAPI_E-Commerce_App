# This module defines custom exceptions for database-related errors.
class DatabaseError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class DatabaseConnectionError(DatabaseError):
    """Raised when there is a connection issue with the database"""
    pass

class DatabaseIntegrityError(DatabaseError):
    """Raised when there is an integrity issue with the database"""
    pass

class DatabaseOperationError(DatabaseError):
    """Raised when there is an operation issue with the database"""
    pass

class DatabaseTimeoutError(DatabaseError):
    """Raised when there is a timeout issue with the database"""
    pass

class DatabaseTransactionError(DatabaseError):
    """Raised when there is a transaction issue with the database"""
    pass

class DatabaseProgrammingError(DatabaseError):
    """Raised when there is a programming issue with the database"""
    pass

class DatabaseTableNotFoundError(DatabaseError):
    """Raised when a database table is not found"""
    def __init__(self, table_name: str):
        super().__init__(
            message=f"Table: '{table_name}' does not exist. Did you run database migrations? or table name is correct/deleted/not created?",
            status_code=500
        )