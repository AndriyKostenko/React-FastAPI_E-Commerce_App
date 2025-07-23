from typing import List
from uuid import uuid4, UUID
from datetime import timezone, datetime

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Index, DateTime
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from shared.models_base_class import Base
from models.mixins import TimestampMixin


class ProductCategory(Base, TimestampMixin):
    __tablename__ = 'product_categories'
    
    __table_args__ = (
        Index('idx_product_categories_name', 'name'),
        Index('idx_product_categories_date_created', 'date_created'),
        Index('idx_product_categories_image_url', 'image_url'),
    )   

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    image_url: Mapped[str] = mapped_column(nullable=False)

    products: Mapped[List['Product']] = relationship('Product', back_populates='category', cascade='all, delete-orphan')