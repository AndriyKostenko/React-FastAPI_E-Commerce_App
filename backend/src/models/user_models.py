from typing import List
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from datetime import timezone
from src.models import Base
from sqlalchemy import String
from src.utils.generate_uuid import generate_uuid


class User(Base):
    __tablename__ = 'users'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid, unique=True)
    name: Mapped[str] = mapped_column(nullable=False)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(nullable=True)
    phone_number: Mapped[str] = mapped_column(nullable=True)
    image: Mapped[str] = mapped_column(nullable=True)
    date_created: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc).astimezone(timezone.utc).replace(tzinfo=None),
        nullable=False
    )
    date_updated: Mapped[datetime] = mapped_column(nullable=True)

    reviews: Mapped[List['ProductReview']] = relationship('ProductReview', back_populates='user')
    addresses: Mapped[List['OrderAddress']] = relationship('OrderAddress', back_populates='user')
    orders: Mapped[List['Order']] = relationship('Order', back_populates='user')

    def __repr__(self):
        return f"<User: {self.name} has been created on {self.date_created} UTC.>"