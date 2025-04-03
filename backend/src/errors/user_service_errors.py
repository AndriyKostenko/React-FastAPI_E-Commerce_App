from typing import Dict, Type


# using Factory Pattern along with Inheritance design patterns for creating user related service errors
class UserServerError(Exception):
    """Base class for user errors"""
    def __init__(self, detail: str):
        super().__init__(detail)
        
class UserNotFoundError(UserServerError):
    """Raised when user is not found"""
    pass


class UserCreationError(UserServerError):
    """Raised when user creation fails"""
    pass

class UserValidationError(UserServerError):
    """Raised when user validation fails"""
    pass

class UserUpdateError(UserServerError):
    """Raised when user update fails"""
    pass

class UserDeletionError(UserServerError):
    """Raised when user deletion fails"""
    pass

class UserAuthenticationError(UserServerError):
    """Raised when user authentication fails"""
    pass




class UserErrorFactory:
    """Factory class to create user errors"""
    
    _error_types: Dict[str, Type[UserServerError]] = {
        'not_found': UserNotFoundError,
        'creation': UserCreationError,
        'validation': UserValidationError,
        'update': UserUpdateError,
        'deletion': UserDeletionError,
        'authentication': UserAuthenticationError
    }
    
    @classmethod
    def create_error(cls, error_type: str, detail: str) -> UserServerError:
        """Create a user error"""
        if error_type not in cls._error_types:
            raise ValueError(f"Unknown error type: {error_type}")
        return cls._error_types[error_type](detail)
    
        
user_service_error_factory = UserErrorFactory()