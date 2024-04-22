from datetime import timedelta, datetime
from typing import List, Annotated

from fastapi import HTTPException, Depends, status, APIRouter
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse

from app.db.crud_user import create_user, get_user_by_email, get_users, delete_user_
from app.db.database_setup import get_db
from app.security.deps import get_current_user
from app.schemas.users_schema import UserSignUp, UserInfo, TokenSchema
from app.security.security import verify_password
from jose import jwt

route = APIRouter(tags=['users'])

SECRET_KEY = '2cdb4dd191cda79010e87dad5c2fbfe392af0ba1b13d2a27c956e406df6ce3a5'
ALGORITHM = 'HS256'


# taking email for authentication coz its unique (but OAth2 form it will be 'username')
async def authenticate_user(email: str, password: str, db):
    db_user = await get_user_by_email(db, user_email=email)
    if not db_user:
        return False
    if not verify_password(password=password, hashed_pass=db_user.hashed_password):
        return False
    return db_user


def create_access_token(email: str, user_id: int, expires_delta: timedelta):
    encode = {'sub': email,
              'id': user_id}
    expires = datetime.utcnow() + expires_delta
    encode.update({'exp': expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)


# registering new user...response model will be full user info
@route.post("/register", summary="Create new user", status_code=status.HTTP_201_CREATED)
async def add_user(user: UserSignUp, db: Session = Depends(get_db)):
    db_user = await get_user_by_email(db, user_email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered!")
    user = await create_user(db=db, user=user)
    return user


# getting token if user is authenticated
@route.post("/token", response_model=TokenSchema)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                                 db: Session = Depends(get_db)):
    user = await authenticate_user(email=form_data.username, password=form_data.password, db=db)
    if not user:
        return 'Failed authentication'
    token = create_access_token(user.email, user.id, timedelta(minutes=20))
    return {'access_token': token, 'token_type': 'bearer'}
