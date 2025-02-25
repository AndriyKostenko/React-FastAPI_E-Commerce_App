from sqlalchemy.orm import declarative_base
from passlib.context import CryptContext

# Base class for all models
Base = declarative_base()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
