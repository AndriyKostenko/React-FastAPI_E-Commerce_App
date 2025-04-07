from fastapi import HTTPException, status


# using a Static Factory Method pattern to create HTTPException instances for user related errors
class UserAPIHTTPErrors:
    @staticmethod
    def user_already_exists() -> HTTPException:
        return HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="User already exists")

    @staticmethod
    def user_not_authenticated() -> HTTPException:
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Could not validate user')
        
    @staticmethod
    def user_not_verified() -> HTTPException:
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='User not verified via Email link')

    @staticmethod
    def user_creation_error(error:str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=str(error))
        
    @staticmethod
    def user_not_found() -> HTTPException:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail='User not found')
        
    @staticmethod
    def unauthorized_user() -> HTTPException:
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Unauthorized')
        
    @staticmethod
    def validation_error(error) -> HTTPException:
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=str(error['detail']['msg']))
        
    @staticmethod
    def invalid_token() -> HTTPException:
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Invalid token')
        
    @staticmethod
    def user_is_not_active() -> HTTPException:
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Your account has been deactivated')
        
user_api_http_errors = UserAPIHTTPErrors()