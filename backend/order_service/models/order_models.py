from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from shared.models.models_base_class import Base
from shared.models_mixins import TimestampMixin


class Order(Base, TimestampMixin):
    __tablename__ = 'orders'

    __table_args__ = (
        Index('idx_users_id', 'user_id'),
        Index('idx_orders_status', 'status'),
        Index('idx_orders_delivery_status', 'delivery_status'),
        Index('idx_orders_date_created', 'date_created'),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True)
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    user_email: Mapped[str] = mapped_column(nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    delivery_status: Mapped[str] = mapped_column(nullable=False)
    payment_intent_id: Mapped[str] = mapped_column(unique=True, nullable=True)
    address_id: Mapped[UUID] = mapped_column(ForeignKey('order_addresses.id'), nullable=False)

    address: Mapped['OrderAddress'] = relationship('OrderAddress', back_populates='orders')
    items: Mapped[list['OrderItem']] = relationship('OrderItem', back_populates='order')

    @classmethod
    def get_search_fields(cls) -> list[str]:
        """Return list of fields to be used in search operations"""
        return ["status", "delivery_status", "payment_intent_id"]

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
            'BOOLEAN': 'boolean',
            'DATETIME': 'datetime',
            'DATE': 'date',
            'JSON': 'mixed',
            'UUID': 'uuid',
        }

        type_name = sql_type.__class__.__name__.upper()
        return type_mapping.get(type_name, 'string')
