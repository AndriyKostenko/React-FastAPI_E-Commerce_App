from decimal import Decimal
from typing import List
from uuid import UUID, uuid4

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from models import Base
from models.mixins import TimestampMixin


class Product(Base, TimestampMixin):
    __tablename__ = 'products'
    
    # Creating indexes for the Product table 
    __table_args__ = (
        Index('idx_product_name', 'name'),
        Index('idx_product_category', 'category_id'),
        Index('idx_product_brand', 'brand'),
        Index('idx_product_in_stock', 'in_stock'),
        Index('idx_product_date_created', 'date_created'),
        Index('idx_product_date_updated', 'date_updated'),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=True)
    category_id: Mapped[UUID] = mapped_column(ForeignKey('product_categories.id'), nullable=False)
    brand: Mapped[str] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[Decimal] = mapped_column(nullable=False)
    in_stock: Mapped[bool] = mapped_column(nullable=False)

    reviews: Mapped[List['ProductReview']] = relationship('ProductReview', back_populates='product', cascade='all, delete-orphan') # type: ignore
    images: Mapped[List['ProductImage']] = relationship('ProductImage', back_populates='product', cascade='all, delete-orphan')
    category: Mapped['ProductCategory'] = relationship('ProductCategory', back_populates='products') # type: ignore


class ProductImage(Base, TimestampMixin):
    __tablename__ = 'product_images'
    
    __table_args__ = (
        Index('idx_product_image_product_id', 'product_id'),
        Index('idx_product_image_date_created', 'date_created'),
        Index('idx_product_image_date_updated', 'date_updated'),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True)
    product_id: Mapped[UUID] = mapped_column(ForeignKey('products.id'), nullable=False)
    image_url: Mapped[str] = mapped_column(nullable=False)
    image_color: Mapped[str] = mapped_column(nullable=True)
    image_color_code: Mapped[str] = mapped_column(nullable=True)


    product: Mapped['Product'] = relationship('Product', back_populates='images')






