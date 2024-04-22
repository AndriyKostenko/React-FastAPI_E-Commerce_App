from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from typing import Union, Any
import jwt
from passlib.context import CryptContext


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # 30 minutes
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days
ALGORITHM = "HS256"
JWT_SECRET_KEY = '123456789'  # should be kept secret
JWT_REFRESH_SECRET_KEY = '987654321'    # should be kept secret


def get_hashed_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, hashed_pass: str) -> bool:
    return password_context.verify(password, hashed_pass)


