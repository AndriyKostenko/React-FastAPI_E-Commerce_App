from typing import Dict, Type


# using Factory Pattern along with Inheritance design patterns for creating user related service errors
class UserServiceError(Exception):
    """Base class for user errors"""
    def __init__(self, detail: str):
        super().__init__(detail)
        
class UserNotFoundError(UserServiceError):
    """Raised when user is not found"""
    pass

class UserAlreadyExistsError(UserServiceError):
    """Raised when user already exists"""
    pass

class UserCreationError(UserServiceError):
    """Raised when user creation fails"""
    pass

class UserValidationError(UserServiceError):
    """Raised when user validation fails"""
    pass

class UserUpdateError(UserServiceError):
    """Raised when user update fails"""
    pass

class UserDeletionError(UserServiceError):
    """Raised when user deletion fails"""
    pass

class UserAuthenticationError(UserServiceError):
    """Raised when user authentication fails"""
    pass

class UserPasswordError(UserServiceError):
    """Raised when user password is invalid"""
    pass

class UserEmailError(UserServiceError):
    """Raised when user email is not verified"""
    pass

class UserServiceDatabaseError(UserServiceError):
    """Raised when there is a database error"""
    pass

class UserIsNotVerifiedError(UserServiceError):
    """Raised when user is not verified"""
    pass





