from uuid import UUID, uuid4

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from shared.models_base_class import Base
from models.mixins import TimestampMixin



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


    product: Mapped['Product'] = relationship('Product', back_populates='images') # type: ignore