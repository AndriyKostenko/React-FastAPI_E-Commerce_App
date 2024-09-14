from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs
from passlib.context import CryptContext

# Base class for all models
class Base(DeclarativeBase, AsyncAttrs):
    pass

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
