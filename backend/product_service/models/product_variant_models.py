from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Index, inspect, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from shared.models.models_base_class import Base
from shared.utils.models_mixins import TimestampMixin


class ProductVariant(Base, TimestampMixin):
    __tablename__ = 'product_variants'

    __table_args__ = (
        Index('idx_product_variant_product_id', 'product_id'),
        Index('idx_product_variant_vid', 'vid'),
        UniqueConstraint('product_id', 'vid', name='uq_product_variant_product_id_vid'),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True)
    product_id: Mapped[UUID] = mapped_column(ForeignKey('products.id'), nullable=False)
    vid: Mapped[str] = mapped_column(nullable=False)
    variant_key: Mapped[str | None] = mapped_column(nullable=True)
    variant_name_en: Mapped[str | None] = mapped_column(nullable=True)
    variant_sku: Mapped[str | None] = mapped_column(nullable=True)
    barcode: Mapped[str | None] = mapped_column(nullable=True)
    variant_image: Mapped[str | None] = mapped_column(nullable=True)
    variant_weight: Mapped[Decimal | None] = mapped_column(nullable=True)
    variant_length: Mapped[int | None] = mapped_column(nullable=True)
    variant_width: Mapped[int | None] = mapped_column(nullable=True)
    variant_height: Mapped[int | None] = mapped_column(nullable=True)
    variant_sell_price: Mapped[Decimal | None] = mapped_column(nullable=True)
    variant_sug_sell_price: Mapped[Decimal | None] = mapped_column(nullable=True)
    inventory_num: Mapped[int | None] = mapped_column(nullable=True)

    product: Mapped['Product'] = relationship('Product', back_populates='variants') # pyright: ignore[reportUndefinedVariable]

    @classmethod
    def get_relations(cls) -> list[str]:
        """Return list of related entities to be loaded with the product variants"""
        return ["product"]

    @classmethod
    def get_search_fields(cls) -> list[str]:
        return ["variant_name_en", "variant_sku", "variant_key"]

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
            'NUMERIC': 'number',
            'DECIMAL': 'number',
            'BOOLEAN': 'boolean',
            'DATETIME': 'datetime',
            'DATE': 'date',
            'JSON': 'mixed',
            'UUID': 'uuid',
        }

        type_name = sql_type.__class__.__name__.upper()
        return type_mapping.get(type_name, 'string')

    def __repr__(self):
        return f"<ProductVariant(id={self.id}, product_id={self.product_id}, vid={self.vid}, variant_key={self.variant_key})>"

    def __str__(self):
        return f"ProductVariant(id={self.id}, product_id={self.product_id}, vid={self.vid}, variant_key={self.variant_key})"
