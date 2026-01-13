from shared.base_exceptions import BaseAPIException


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
