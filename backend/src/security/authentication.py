from datetime import timedelta, datetime
from typing import Annotated
from fastapi import HTTPException, Depends, status, APIRouter
from pydantic import ValidationError
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.db_setup import get_db_session
from src.service.user_service import UserCRUDService

# specify the route of created token...in my case its /token
oath2_bearer = OAuth2PasswordBearer(tokenUrl='token')


def create_access_token(email: str, user_id: int, role: str, expires_delta: timedelta):
    encode = {'sub': email,
              'id': user_id,
              'role': role}
    expires = datetime.utcnow() + expires_delta
    encode.update({'exp': expires})
    return jwt.encode(encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# checking if user is logged in and with valid token
async def get_current_user(token: Annotated[str, Depends(oath2_bearer)]):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get('sub')
        user_id: int = payload.get('id')
        user_role: str = payload.get('role')
        if email is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate user')
        return {'email': email, 'id': user_id, 'user_role': user_role}
    except (JWTError, ValidationError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Could not validate user')


# Dependency to get authenticated user
async def get_authenticated_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                                 session: AsyncSession = Depends(get_db_session)):
    user = await UserCRUDService(session).authenticate_user(email=form_data.username,
                                                            entered_password=form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Could not validate user')
    return user


