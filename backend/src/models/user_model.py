from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy import Sequence, ForeignKey, Column, Integer, String, Text, DateTime
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Base(DeclarativeBase, AsyncAttrs):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, unique=True)
    name: Mapped[str] = mapped_column(unique=False, nullable=False)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(unique=False, nullable=False)
    role: Mapped[str] = mapped_column(unique=False, nullable=True)
    phone_number: Mapped[str] = mapped_column(unique=False, nullable=True)
    date_created: Mapped[datetime] = mapped_column(default=datetime.utcnow, unique=False, nullable=False)

    def __repr__(self):
        return f"<User: {self.name} has been created on {self.date_created} UTC.>"
