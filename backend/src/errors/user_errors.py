
class UserServerError(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        
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