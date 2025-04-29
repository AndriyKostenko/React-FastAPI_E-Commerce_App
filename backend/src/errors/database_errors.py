# This module defines custom exceptions for database-related errors.
class DatabaseError(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)

class DatabaseConnectionError(DatabaseError):
    """Raised when there is a connection issue with the database"""
    pass

class DatabaseSessionError(DatabaseError):
    """Raised when there is a session issue with the database"""
    pass

