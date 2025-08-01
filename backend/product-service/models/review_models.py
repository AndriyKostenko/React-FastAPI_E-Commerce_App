from uuid import uuid4, UUID
from datetime import datetime, timezone

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, Index
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from shared.models_base_class import Base
from models.mixins import TimestampMixin


class ProductReview(Base, TimestampMixin):
    __tablename__ = 'product_reviews'
    
    __table_args__ = (
        Index('idx_product_review_user_id', 'user_id'),
        Index('idx_product_review_product_id', 'product_id'),
        Index('idx_product_review_date_created', 'date_created'),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True)
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey('products.id'), nullable=False)
    comment: Mapped[str] = mapped_column(nullable=True)
    rating: Mapped[float] = mapped_column(nullable=True)


    product: Mapped['Product'] = relationship('Product', back_populates='reviews')