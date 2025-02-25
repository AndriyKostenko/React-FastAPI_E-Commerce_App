
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