from typing import List

from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy import ForeignKey
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
    image: Mapped[str] = mapped_column(unique=False, nullable=True)

    def __repr__(self):
        return f"<User: {self.name} has been created on {self.date_created} UTC.>"


class Product(Base):
    __tablename__ = 'products'

    id: Mapped[str] = mapped_column(primary_key=True, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(unique=False, nullable=False)
    description: Mapped[str] = mapped_column(unique=False, nullable=True)
    category: Mapped[str] = mapped_column(unique=False, nullable=False)
    brand: Mapped[str] = mapped_column(unique=False, nullable=False)
    image_url: Mapped[str] = mapped_column(unique=False, nullable=True)
    quantity: Mapped[int] = mapped_column(unique=False, nullable=False)
    price: Mapped[float] = mapped_column(unique=False, nullable=False)


class Order(Base):
    __tablename__ = 'orders'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    amount: Mapped[float] = mapped_column(unique=False, nullable=False)
    currency: Mapped[str] = mapped_column(unique=False, nullable=False)
    status: Mapped[str] = mapped_column(unique=False, nullable=False)
    delivery_status: Mapped[str] = mapped_column(unique=False, nullable=False)
    create_date: Mapped[datetime] = mapped_column(default=datetime.utcnow, unique=False, nullable=False)
    payment_intent_id: Mapped[str] = mapped_column(unique=True, nullable=True)
    address_id: Mapped[int] = mapped_column(ForeignKey('addresses.id'), nullable=False)
    address: Mapped['Address'] = relationship('Address', back_populates='orders')
    items: Mapped[List['OrderItem']] = relationship('OrderItem', back_populates='order')


class OrderItem(Base):
    __tablename__ = 'order_items'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, unique=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'), nullable=False)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id'), nullable=False)
    quantity: Mapped[int] = mapped_column(unique=False, nullable=False)
    price: Mapped[float] = mapped_column(unique=False, nullable=False)
    order: Mapped['Order'] = relationship('Order', back_populates='items')


class Address(Base):
    __tablename__ = 'addresses'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    street: Mapped[str] = mapped_column(unique=False, nullable=True)
    city: Mapped[str] = mapped_column(unique=False, nullable=True)
    province: Mapped[str] = mapped_column(unique=False, nullable=True)
    postal_code: Mapped[str] = mapped_column(unique=False, nullable=True)
    orders: Mapped[List['Order']] = relationship('Order', back_populates='address')


class Category(Base):
    __tablename__ = 'categories'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, unique=True)
    name: Mapped[str] = mapped_column(unique=False, nullable=False)
    description: Mapped[str] = mapped_column(unique=False, nullable=True)
