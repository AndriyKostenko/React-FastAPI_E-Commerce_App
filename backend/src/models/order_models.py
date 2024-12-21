from typing import List
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String
from src.models import Base
from src.utils.generate_uuid import generate_uuid


class Order(Base):
    __tablename__ = 'orders'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid, unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    delivery_status: Mapped[str] = mapped_column(nullable=False)
    date_created: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc).astimezone(timezone.utc).replace(tzinfo=None),
        nullable=False
    )
    date_updated: Mapped[datetime] = mapped_column(nullable=True)
    payment_intent_id: Mapped[str] = mapped_column(unique=True, nullable=True)
    address_id: Mapped[str] = mapped_column(ForeignKey('order_addresses.id'), nullable=False)

    address: Mapped['OrderAddress'] = relationship('OrderAddress', back_populates='orders')
    items: Mapped[List['OrderItem']] = relationship('OrderItem', back_populates='order')
    user: Mapped['User'] = relationship('User', back_populates='orders')


class OrderItem(Base):
    __tablename__ = 'order_items'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid, unique=True)
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.id'), nullable=False)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id'), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[float] = mapped_column(nullable=False)

    order: Mapped['Order'] = relationship('Order', back_populates='items')
    product: Mapped['Product'] = relationship('Product')


class OrderAddress(Base):
    __tablename__ = 'order_addresses'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid, unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False)
    street: Mapped[str] = mapped_column(nullable=True)
    city: Mapped[str] = mapped_column(nullable=True)
    province: Mapped[str] = mapped_column(nullable=True)
    postal_code: Mapped[str] = mapped_column(nullable=True)

    orders: Mapped[List['Order']] = relationship('Order', back_populates='address')
    user: Mapped['User'] = relationship('User', back_populates='addresses')

