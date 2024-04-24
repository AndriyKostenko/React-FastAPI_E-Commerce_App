from datetime import timedelta
from typing import Annotated

from fastapi import Depends, APIRouter, status, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.db_setup import get_db_session
from src.schemas.user_schemas import UserSignUp, UserInfo, TokenSchema, GetUser
from src.security.authentication import create_access_token, get_authenticated_user
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
        raise HTTPException(status_code=400, detail="Email already registered!")
    new_db_user = await UserCRUDService(session).create_user(user)
    return new_db_user


@user_routes.post("/login")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                session: AsyncSession = Depends(get_db_session)):
    user = await UserCRUDService(session).authenticate_user(email=form_data.username,
                                                            entered_password=form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Could not validate user')
    return {"message": "User authenticated successfully"}


@user_routes.post("/token", response_model=TokenSchema)
async def generate_token(user: UserInfo = Depends(get_authenticated_user)):
    token = create_access_token(user.email, user.id, user.role, timedelta(minutes=20))
    return {"access_token": token, "token_type": "bearer"}



