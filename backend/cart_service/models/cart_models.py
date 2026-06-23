from uuid import UUID, uuid4
from decimal import Decimal
from typing import Any, override

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, ForeignKey, Numeric, inspect
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from shared.models.models_base_class import Base
from shared.utils.models_mixins import TimestampMixin


class Cart(Base, TimestampMixin):
    __tablename__: str = 'carts'

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True)
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False, unique=True, index=True)

    items: Mapped[list["CartItem"]] = relationship(
        "CartItem", 
        back_populates="cart", 
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
        return f"Cart(id={self.id}, user_id={self.user_id}, date_created={self.date_created}, date_updated={self.date_updated})"

    @override
    def __str__(self) -> str:
        return f"Cart(id={self.id}, user_id={self.user_id})"


class CartItem(Base, TimestampMixin):
    __tablename__: str = 'cart_items'

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True)
    cart_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("carts.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    price_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")

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
            'NUMERIC': 'number',
            'DECIMAL': 'number'
        }

        type_name = sql_type.__class__.__name__.upper()
        return type_mapping.get(type_name, 'string')

    @override
    def __repr__(self) -> str:
        return f"CartItem(id={self.id}, cart_id={self.cart_id}, product_id={self.product_id}, quantity={self.quantity}, price_snapshot={self.price_snapshot}, date_created={self.date_created}, date_updated={self.date_updated})"

    @override
    def __str__(self) -> str:
        return f"CartItem(id={self.id}, cart_id={self.cart_id}, product_id={self.product_id}, quantity={self.quantity})"
