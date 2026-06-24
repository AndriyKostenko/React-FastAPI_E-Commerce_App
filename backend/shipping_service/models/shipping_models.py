from datetime import datetime
from decimal import Decimal
from typing import Any, override
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from shared.models.models_base_class import Base
from shared.utils.models_mixins import TimestampMixin


class ShippingMethod(Base, TimestampMixin):
    __tablename__: str = "shipping_methods"

    __table_args__ = (
        Index("idx_shipping_methods_is_active", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    carrier: Mapped[str] = mapped_column(String(100), nullable=False)
    base_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    estimated_days: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    shipments: Mapped[list["Shipment"]] = relationship(
        "Shipment", back_populates="method", lazy="selectin"
    )

    @classmethod
    def get_admin_schema(cls) -> list[dict[str, str]]:
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

    @override
    def __repr__(self) -> str:
        return f"ShippingMethod(id={self.id}, name={self.name}, carrier={self.carrier})"


class Shipment(Base, TimestampMixin):
    __tablename__: str = "shipments"

    __table_args__ = (
        Index("idx_shipments_order_id", "order_id", unique=True),
        Index("idx_shipments_user_id", "user_id"),
        Index("idx_shipments_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True
    )
    order_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=False, unique=True
    )
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    method_id: Mapped[UUID] = mapped_column(
        ForeignKey("shipping_methods.id"), nullable=False
    )
    tracking_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    estimated_delivery: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    method: Mapped["ShippingMethod"] = relationship(
        "ShippingMethod", back_populates="shipments", lazy="selectin"
    )

    @classmethod
    def get_admin_schema(cls) -> list[dict[str, str]]:
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

    @override
    def __repr__(self) -> str:
        return f"Shipment(id={self.id}, order_id={self.order_id}, status={self.status})"
