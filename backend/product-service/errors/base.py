from typing import Any, Dict

from fastapi import HTTPException


# using Factory Pattern along with Inheritance design patterns for creating Product related service errors
class BaseAPIException(HTTPException):
    """Base class for all API exceptions."""
    def __init__(self, status_code: int, detail: Any = None, headers: Dict[str, str] | None = None):
        super().__init__(status_code=status_code, detail=detail)
        self.headers = headers


        
#------Database Service Errors------

class DatabaseConnectionError(BaseAPIException):
    """Raised when there is a connection issue with the database"""
    def __init__(self, detail: str = "Database connection error"):
        super().__init__(detail=detail, status_code=500)

class DatabaseSessionError(BaseAPIException):
    """Raised when there is a session issue with the database"""
    def __init__(self, detail: str = "Database session error"):
        super().__init__(detail=detail, status_code=500)


#------Rate Limiter Service Errors------

class RateLimitExceededError(BaseAPIException):
    """Exception raised when rate limit is exceeded"""
    def __init__(self, client_ip: str, retry_after: int, status_code: int = 429):
        detail = {
            "message": f"Too many requests from: {client_ip}",
            "retry_after": retry_after
        }
        headers = {"Retry-After": str(retry_after)}
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers=headers
        )





