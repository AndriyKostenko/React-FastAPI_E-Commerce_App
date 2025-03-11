from datetime import timedelta
from typing import Annotated

from fastapi import Depends, APIRouter, status, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession


from src.security.authentication import auth_manager
from src.config import settings
from src.db.db_setup import get_db_session
from src.schemas.user_schemas import UserSignUp, UserInfo, TokenSchema, UserLoginDetails
# from src.security.authentication import create_access_token, get_authenticated_user, get_current_user
from src.service.user_service import UserCRUDService
from src.errors.user_errors import UserCreationError
from src.errors.database_errors import DatabaseError
from src.errors.user_http_responses import UserAPIHTTPErrors

user_routes = APIRouter(
    tags=["user"]
)


# registering new user...response_model will return the neccesary data...
# validation errors will be handeled automatically by pydantic and fastapi and sent 422
@user_routes.post('/register',
                  summary="Create new user",
                  status_code=status.HTTP_201_CREATED,
                  response_model=UserInfo,
                  response_description="New user created successfully",
                  responses={
                        409: {"description": "User already exists"},
                        201: {"description": "New user created successfully"},
                        500: {"description": "Internal server error"},
                        422: {"description": "Validation error"}
                        
                  })
async def create_user(user: UserSignUp, 
                      session: AsyncSession = Depends(get_db_session)) -> UserInfo:
    try:
        new_db_user = await UserCRUDService(session=session).create_user(user=user)
    except UserCreationError as error:
        raise UserAPIHTTPErrors.user_already_exists()
    except DatabaseError as error:
        raise UserAPIHTTPErrors.user_creation_error(error=error)
    return new_db_user


@user_routes.post("/login",
                  summary="User login",
                  status_code=status.HTTP_200_OK,
                  response_model=UserLoginDetails,
                  response_description="User logged in successfully",
                  responses={
                      401: {"description": "Could not validate user"},
                      200: {"description": "User logged in successfully"}
                  })
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                session: AsyncSession = Depends(get_db_session)) -> UserLoginDetails:
    user = await auth_manager.get_authenticated_user(form_data=form_data, session=session)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Could not validate user')
    # create access token
    access_token = auth_manager.create_access_token(user.email, 
                                                    user.id, 
                                                    user.role, 
                                                    timedelta(minutes=settings.TIME_DELTA_MINUTES))
    # get token expiry
    token_data = await auth_manager.get_current_user(access_token)
    
    return UserLoginDetails(access_token=access_token,
                            token_type=settings.TOKEN_TYPE,
                            user_role=user.role,
                            token_expiry=token_data['exp'],
                            user_id=user.id)



@user_routes.post("/token", 
                  response_model=TokenSchema,
                  response_description="New token generated successfully",
                  responses={
                      401: {"description": "Could not validate user"},
                      200: {"description": "New token generated successfully"}
                  })
async def generate_token(user: UserInfo = Depends(auth_manager.get_authenticated_user)) -> TokenSchema:
    token = auth_manager.create_access_token(user.email, user.id, user.role, timedelta(minutes=settings.TIME_DELTA_MINUTES))
    return TokenSchema(access_token=token, token_type=settings.TOKEN_TYPE)


@user_routes.get("/me")
async def get_current_user_data(current_user: Annotated[dict, Depends(auth_manager.get_current_user)]):
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')
    return current_user


@user_routes.get("/user/{user_email}")
async def get_user_by_email(user_email: str, session: AsyncSession = Depends(get_db_session)):
    user = await UserCRUDService(session).get_user_by_email(user_email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    return user

@user_routes.post("/user/{id}")
async def get_user_by_id(id: str, session: AsyncSession = Depends(get_db_session)):
    user = await UserCRUDService(session).get_user_by_id(id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    return user
