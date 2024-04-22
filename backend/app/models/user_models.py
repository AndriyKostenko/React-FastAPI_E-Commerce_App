from sqlalchemy import Sequence, ForeignKey, Column, Integer, String, Text, DateTime
from app.db.database_setup import Base


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=False)
    email = Column(String, primary_key=True, unique=True, nullable=False)
    hashed_password = Column(String, unique=True, nullable=False)


