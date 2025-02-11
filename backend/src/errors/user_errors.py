from fastapi import HTTPException

class UserServerError(HTTPException):
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)
        
        
class UserNotFoundError(UserServerError):
    pass


class UserCreationError(UserServerError):
    pass

class UserValidationError(UserServerError):
    pass

class UserUpdateError(UserServerError):
    pass

class UserDeletionError(UserServerError):
    pass

class UserAuthenticationError(UserServerError):
    pass