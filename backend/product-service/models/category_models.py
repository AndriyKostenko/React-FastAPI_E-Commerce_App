from typing import List, Any
from uuid import uuid4, UUID


from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Index, inspect
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from shared.models.models_base_class import Base
from shared.models_mixins import TimestampMixin


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

    products: Mapped[List['Product']] = relationship('Product', back_populates='category', cascade='all, delete-orphan') #type: ignore
    
    @classmethod
    def get_search_fields(cls) -> list[str]:
        """Return list of fields to be used in search operations"""
        return ["name"]
    
    @classmethod
    def get_relations(cls) -> list[str]:
        """Return list of related entities to be loaded with the product"""
        return ["products"]
    
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
            'BOOLEAN': 'boolean',
            'DATETIME': 'datetime',
            'DATE': 'date',
            'JSON': 'mixed',
            'UUID': 'uuid',
        }
        
        type_name = sql_type.__class__.__name__.upper()
        return type_mapping.get(type_name, 'string')
    
    def __repr__(self):
        return f"<ProductCategory(id={self.id}, name={self.name}, image_url={self.image_url})>"
    def __str__(self):
        return f"ProductCategory(id={self.id}, name={self.name}, image_url={self.image_url})"