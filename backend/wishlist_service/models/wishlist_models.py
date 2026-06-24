from uuid import UUID, uuid4
from typing import Any, override

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, inspect, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from shared.models.models_base_class import Base
from shared.utils.models_mixins import TimestampMixin


class Wishlist(Base, TimestampMixin):
    __tablename__: str = 'wishlists'

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True)
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False, unique=True, index=True)

    items: Mapped[list["WishlistItem"]] = relationship(
        "WishlistItem",
        back_populates="wishlist",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

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

    @override
    def __repr__(self) -> str:
        return f"Wishlist(id={self.id}, user_id={self.user_id}, date_created={self.date_created}, date_updated={self.date_updated})"

    @override
    def __str__(self) -> str:
        return f"Wishlist(id={self.id}, user_id={self.user_id})"


class WishlistItem(Base, TimestampMixin):
    __tablename__: str = 'wishlist_items'

    __table_args__ = (
        UniqueConstraint('wishlist_id', 'product_id', name='uq_wishlist_item_product'),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True)
    wishlist_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("wishlists.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False, index=True)

    wishlist: Mapped["Wishlist"] = relationship("Wishlist", back_populates="items")

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

    @override
    def __repr__(self) -> str:
        return f"WishlistItem(id={self.id}, wishlist_id={self.wishlist_id}, product_id={self.product_id}, date_created={self.date_created}, date_updated={self.date_updated})"

    @override
    def __str__(self) -> str:
        return f"WishlistItem(id={self.id}, wishlist_id={self.wishlist_id}, product_id={self.product_id})"
