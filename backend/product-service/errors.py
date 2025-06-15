from typing import Any, Dict, Optional

from fastapi import HTTPException


# using Factory Pattern along with Inheritance design patterns for creating Product related service errors
class BaseAPIException(HTTPException):
    """Base class for all API exceptions."""
    def __init__(self, status_code: int, detail: Any = None, headers: Dict[str, str] | None = None):
        super().__init__(status_code=status_code, detail=detail)
        self.headers = headers

#------Product Service Errors------
        
class ProductNotFoundError(BaseAPIException):
    """Raised when Product is not found"""
    def __init__(self, detail: str = "Product not found"):
        super().__init__(detail=detail, status_code=404)

class ProductAlreadyExistsError(BaseAPIException):
    """Raised when Product already exists"""
    def __init__(self, detail: str = "Product already exists"):
        super().__init__(detail=detail, status_code=409)

class ProductCreationError(BaseAPIException):
    """Raised when Product creation fails"""
    def __init__(self, detail: str = "Product creation failed"):
        super().__init__(detail=detail, status_code=500)

class ProductValidationError(BaseAPIException):
    """Raised when Product validation fails"""
    def __init__(self, detail: str = "Product validation failed"):
        super().__init__(detail=detail, status_code=422)

class ProductUpdateError(BaseAPIException):
    """Raised when Product update fails"""
    def __init__(self, detail: str = "Product update failed"):
        super().__init__(detail=detail, status_code=500)

class ProductDeletionError(BaseAPIException):
    """Raised when Product deletion fails"""
    def __init__(self, detail: str = "Product deletion failed"):
        super().__init__(detail=detail, status_code=500)
        
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





