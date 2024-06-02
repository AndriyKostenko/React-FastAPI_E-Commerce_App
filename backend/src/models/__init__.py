from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs
from passlib.context import CryptContext


class Base(DeclarativeBase, AsyncAttrs):
    pass


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
