from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Index, inspect
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from shared.models.models_base_class import Base
from shared.models_mixins import TimestampMixin



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
    
    
    @classmethod
    def get_relations(cls) -> list[str]:
        """Return list of related entities to be loaded with the product_images"""
        return ["product"]
    
    @classmethod
    def get_search_fields(cls) -> list[str]:
        return ["product_id"]
    
    @classmethod
    def get_admin_schema(cls) -> list[dict[str, Any]]:
        """Get schema information for AdminJS"""
        inspector = inspect(cls)
        fields = []
        
        for column in inspector.columns:
            field_info = {
                "path": column.name,
                "type": cls._map_sqlalchemy_type_to_adminjs(column.type),
                "isId": column.primary_key,
            }
            fields.append(field_info)
        
        return fields
    
    @staticmethod
    def _map_sqlalchemy_type_to_adminjs(sql_type) -> str:
        """Map SQLAlchemy types to AdminJS types"""
        type_mapping = {
            'VARCHAR': 'string',
            'TEXT': 'string',
            'INTEGER': 'number',
            'BIGINT': 'number',
            'FLOAT': 'number',
            'NUMERIC': 'number',  # Added for Decimal type
            'DECIMAL': 'number',  # Alternative name for Decimal
            'BOOLEAN': 'boolean',
            'DATETIME': 'datetime',
            'DATE': 'date',
            'JSON': 'mixed',
            'UUID': 'uuid',
        }
        
        type_name = sql_type.__class__.__name__.upper()
        return type_mapping.get(type_name, 'string')
    
    def __repr__(self):
        return f"<ProductImage(id={self.id}, product_id={self.product_id}, image_url={self.image_url})>"
    def __str__(self):
        return f"ProductImage(id={self.id}, product_id={self.product_id}, image_url={self.image_url})"