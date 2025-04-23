from sqlalchemy.orm import DeclarativeBase
from passlib.context import CryptContext

# Base class for all models
class Base(DeclarativeBase):
    pass

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
