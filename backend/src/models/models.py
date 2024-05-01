from typing import List

from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy import Sequence, ForeignKey, Column, Integer, String, Text, DateTime, Float
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


class Product(Base):
    __tablename__ = 'products'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, unique=True)
    name: Mapped[str] = mapped_column(unique=False, nullable=False)
    description: Mapped[str] = mapped_column(unique=False, nullable=True)
    price: Mapped[Float] = mapped_column(unique=False, nullable=False)
    quantity: Mapped[int] = mapped_column(unique=False, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id'), nullable=False)
    image_url: Mapped[str] = mapped_column(unique=False, nullable=True)


class Category(Base):
    __tablename__ = 'categories'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, unique=True)
    name: Mapped[str] = mapped_column(unique=False, nullable=False)
    description: Mapped[str] = mapped_column(unique=False, nullable=True)


class Order(Base):
    __tablename__ = 'orders'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    date_placed: Mapped[datetime] = mapped_column(default=datetime.utcnow, unique=False, nullable=False)
    status: Mapped[str] = mapped_column(unique=False, nullable=False)


class OrderItem(Base):
    __tablename__ = 'order_items'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, unique=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), nullable=False)
    quantity: Mapped[int] = mapped_column(unique=False, nullable=False)
    price: Mapped[Float] = mapped_column(unique=False, nullable=False)


class Address(Base):
    __tablename__ = 'addresses'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    street: Mapped[str] = mapped_column(unique=False, nullable=False)
    city: Mapped[str] = mapped_column(unique=False, nullable=False)
    state: Mapped[str] = mapped_column(unique=False, nullable=False)
    country: Mapped[str] = mapped_column(unique=False, nullable=False)
    zip_code: Mapped[str] = mapped_column(unique=False, nullable=False)


class Cart(Base):
    __tablename__ = 'carts'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    items: Mapped[List['CartItem']] = relationship('CartItem', back_populates='cart')


class CartItem(Base):
    __tablename__ = 'cart_items'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, unique=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey('carts.id'), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), nullable=False)
    quantity: Mapped[int] = mapped_column(unique=False, nullable=False)
    price: Mapped[Float] = mapped_column(unique=False, nullable=False)
    cart: Mapped['Cart'] = relationship('Cart', back_populates='items')
