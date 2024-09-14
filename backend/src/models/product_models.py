from typing import List
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from sqlalchemy import ForeignKey, String
from src.models import Base
from src.utils.generate_uuid import generate_uuid


class Product(Base):
    __tablename__ = 'products'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid, unique=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=True)
    category_id: Mapped[str] = mapped_column(ForeignKey('product_categories.id'), nullable=False)
    brand: Mapped[str] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[float] = mapped_column(nullable=False)
    in_stock: Mapped[bool] = mapped_column(nullable=True)
    date_created: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)

    reviews: Mapped[List['ProductReview']] = relationship('ProductReview', back_populates='product', cascade='all, delete-orphan')
    images: Mapped[List['ProductImage']] = relationship('ProductImage', back_populates='product', cascade='all, delete-orphan')
    category: Mapped['ProductCategory'] = relationship('ProductCategory', back_populates='products')


class ProductImage(Base):
    __tablename__ = 'product_images'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid, unique=True)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id'), nullable=False)
    image_url: Mapped[str] = mapped_column(nullable=False)
    image_color: Mapped[str] = mapped_column(nullable=True)
    image_color_code: Mapped[str] = mapped_column(nullable=True)

    product: Mapped['Product'] = relationship('Product', back_populates='images')


class ProductReview(Base):
    __tablename__ = 'product_reviews'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid, unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ), nullable=False)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id'), nullable=False)
    rating: Mapped[float] = mapped_column(nullable=False)
    comment: Mapped[str] = mapped_column(nullable=True)
    date_created: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)

    user: Mapped['User'] = relationship('User', back_populates='reviews')
    product: Mapped['Product'] = relationship('Product', back_populates='reviews')


class ProductCategory(Base):
    __tablename__ = 'product_categories'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid, unique=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)

    products: Mapped[List['Product']] = relationship('Product', back_populates='category')
