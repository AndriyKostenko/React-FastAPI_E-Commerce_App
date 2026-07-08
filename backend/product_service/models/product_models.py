from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Index, inspect, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from shared.models.models_base_class import Base
from shared.utils.models_mixins import TimestampMixin


class Product(Base, TimestampMixin):
    __tablename__: str = 'products'

    __table_args__: tuple = (
        # ── Single-column indexes (used for exact filters & FK lookups) ──────
        Index('idx_product_name',       'name'),
        Index('idx_product_brand',      'brand'),
        Index('idx_product_category',   'category_id'),
        Index('idx_product_in_stock',   'in_stock'),
        Index('idx_product_price',      'price'),          # range queries (min_price/max_price)
        Index('idx_product_pid',        'pid', unique=True),

        # ── Composite indexes for the most common query patterns ─────────────
        # "Show in-stock products" sorted by newest — the default browse query
        Index('idx_product_in_stock_date_created', 'in_stock', 'date_created'),
        # "Browse by category, in-stock only" — most common e-commerce filter
        Index('idx_product_category_in_stock', 'category_id', 'in_stock'),
        # "Browse by brand, in-stock only"
        Index('idx_product_brand_in_stock', 'brand', 'in_stock'),
        # Sorting by price within a category
        Index('idx_product_category_price', 'category_id', 'price'),

        # ── Partial index — only indexes in-stock rows ───────────────────────
        # Smallest possible index for the most common filter; Postgres uses this
        # automatically when WHERE in_stock = true is present.
        Index('idx_product_in_stock_partial', 'id', 'date_created',
              postgresql_where='in_stock = true'),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, unique=True)
    pid: Mapped[str | None] = mapped_column(nullable=True, unique=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(nullable=True)
    category_id: Mapped[UUID] = mapped_column(ForeignKey('product_categories.id'), nullable=False)
    brand: Mapped[str] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[Decimal] = mapped_column(nullable=False)
    in_stock: Mapped[bool] = mapped_column(nullable=False)
    sku: Mapped[str | None] = mapped_column(nullable=True)
    image_url: Mapped[str | None] = mapped_column(nullable=True)

    reviews: Mapped[list['ProductReview']] = relationship('ProductReview', back_populates='product', cascade='all, delete-orphan') # pyright: ignore[reportUndefinedVariable]
    images: Mapped[list['ProductImage']] = relationship('ProductImage', back_populates='product', cascade='all, delete-orphan') # pyright: ignore[reportUndefinedVariable]
    variants: Mapped[list['ProductVariant']] = relationship('ProductVariant', back_populates='product', cascade='all, delete-orphan') # pyright: ignore[reportUndefinedVariable]
    category: Mapped['ProductCategory'] = relationship('ProductCategory', back_populates='products') # pyright: ignore[reportUndefinedVariable]

    @classmethod
    def get_search_fields(cls) -> list[str]:
        """Return list of fields to be used in search operations"""
        return ["name", "description", "brand"]

    @classmethod
    def get_relations(cls) -> list[str]:
        """Return list of related entities to be loaded with the product"""
        return ["reviews", "images", "variants", "category"]

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
        return f"<Product(id={self.id}, pid={self.pid}, name={self.name}, category_id={self.category_id}, brand={self.brand}, in_stock={self.in_stock})>"
    def __str__(self):
        return f"Product(id={self.id}, pid={self.pid}, name={self.name}, category_id={self.category_id}, brand={self.brand}, in_stock={self.in_stock})"


# Import variant model here so SQLAlchemy can resolve the relationship at mapper configuration time.
from models.product_variant_models import ProductVariant  # noqa: E402, F401
