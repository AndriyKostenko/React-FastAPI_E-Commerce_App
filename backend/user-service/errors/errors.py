from typing import Any, Dict, Optional

from fastapi import HTTPException


# using Factory Pattern along with Inheritance design patterns for creating user related service errors
class BaseAPIException(HTTPException):
    """Base class for all API exceptions."""
    def __init__(self, status_code: int, detail: Any = None, headers: Dict[str, str] | None = None):
        super().__init__(status_code=status_code, detail=detail)
        self.headers = headers

#------User Service Errors------
        
class UserNotFoundError(BaseAPIException):
    """Raised when user is not found"""
    def __init__(self, detail: str = "User not found"):
        super().__init__(detail=detail, status_code=404)

class UserAlreadyExistsError(BaseAPIException):
    """Raised when user already exists"""
    def __init__(self, detail: str = "User already exists"):
        super().__init__(detail=detail, status_code=409)

class UserCreationError(BaseAPIException):
    """Raised when user creation fails"""
    def __init__(self, detail: str = "User creation failed"):
        super().__init__(detail=detail, status_code=500)

class UserValidationError(BaseAPIException):
    """Raised when user validation fails"""
    def __init__(self, detail: str = "User validation failed"):
        super().__init__(detail=detail, status_code=422)

class UserUpdateError(BaseAPIException):
    """Raised when user update fails"""
    def __init__(self, detail: str = "User update failed"):
        super().__init__(detail=detail, status_code=500)

class UserDeletionError(BaseAPIException):
    """Raised when user deletion fails"""
    def __init__(self, detail: str = "User deletion failed"):
        super().__init__(detail=detail, status_code=500)

class UserAuthenticationError(BaseAPIException):
    """Raised when user authentication fails"""
    def __init__(self, detail: str = "User authentication failed"):
        super().__init__(detail=detail, status_code=401)

class UserPasswordError(BaseAPIException):
    """Raised when user password is invalid"""
    def __init__(self, detail: str = "User password is invalid"):
        super().__init__(detail=detail, status_code=400)

class UserEmailError(BaseAPIException):
    """Raised when user email is not verified"""
    def __init__(self, detail: str = "User email is not verified"):
        super().__init__(detail=detail, status_code=400)

class UserIsNotVerifiedError(BaseAPIException):
    """Raised when user is not verified"""
    def __init__(self, detail: str = "User is not verified"):
        super().__init__(detail=detail, status_code=403)



#------Email Service Errors------

class EmailServiceError(BaseAPIException):
    """Raised when there is an error in the email service"""
    def __init__(self, detail: str = "Email service error"):
        super().__init__(detail=detail, status_code=500)

        
class EmailSendError(BaseAPIException):
    """Raised when there is an error sending the email"""
    def __init__(self, detail: str = "Email send error"):
        super().__init__(detail=detail, status_code=500)
        
class EmailTemplateError(BaseAPIException):    
    """Raised when there is an error in the email template"""
    def __init__(self, detail: str = "Email template error"):
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





