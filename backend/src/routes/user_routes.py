from datetime import timedelta
from typing import Annotated

from fastapi import Depends, APIRouter, status, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.db_setup import get_db_session
from src.schemas.user_schemas import UserSignUp, UserInfo, TokenSchema, GetUser, UserSaveWithGoogle
from src.security.authentication import create_access_token, get_authenticated_user, get_current_user
from src.service.user_service import UserCRUDService

user_routes = APIRouter(
    tags=["user"]
)


# registering new user...response model will be full user info
@user_routes.post('/register',
                  summary="Create new user",
                  status_code=status.HTTP_201_CREATED)
async def create_user(user: UserSignUp, session: AsyncSession = Depends(get_db_session)):
    existing_db_user = await UserCRUDService(session).get_user_by_email(email=user.email)
    if existing_db_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered!")
    new_db_user = await UserCRUDService(session).create_user(user)

    return {"email": new_db_user.email,
            "password": new_db_user.hashed_password}


@user_routes.post("/login",
                  summary="User login",
                  status_code=status.HTTP_200_OK)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                session: AsyncSession = Depends(get_db_session)):
    user = await UserCRUDService(session).authenticate_user(email=form_data.username,
                                                            entered_password=form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Could not validate user')
    return user


@user_routes.post("/token", response_model=TokenSchema)
async def generate_token(user: UserInfo = Depends(get_authenticated_user)):
    token = create_access_token(user.email, user.id, user.role, timedelta(minutes=20))
    return {"access_token": token, "token_type": "bearer"}


@user_routes.get("/current_user")
async def get_current_user(current_user: Annotated[dict, Depends(get_current_user)]):
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')
    return current_user


@user_routes.get("/get_user/{user_email}")
async def get_user(user_email: str, session: AsyncSession = Depends(get_db_session)):
    user = await UserCRUDService(session).get_user_by_email(user_email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    return user
