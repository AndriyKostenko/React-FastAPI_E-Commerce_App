from datetime import datetime
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt
from pydantic import ValidationError

from app.db.crud_user import get_user_by_email
from app.db.database_setup import get_db
from app.schemas.users_schema import TokenPayload
from app.security.security import ALGORITHM, JWT_SECRET_KEY

reusable_oauth = OAuth2PasswordBearer(
    tokenUrl="/login",
    scheme_name="JWT"
)


async def get_current_user(token: str = Depends(reusable_oauth), db: Session = Depends(get_db)) -> dict:
    try:
        payload = jwt.decode(
            token, JWT_SECRET_KEY, algorithms=[ALGORITHM]
        )
        token_data = TokenPayload(**payload)


    except(jwt.PyJWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_email(db=db, user_email=token_data.sub)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find user",
        )

    return {'name': user.name,
            'surname': user.surname,
            'age': user.age,
            'email': user.email}