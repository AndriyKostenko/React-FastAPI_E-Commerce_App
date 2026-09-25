from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, Numeric, inspect, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from models.base import Base
from shared.utils.models_mixins import TimestampMixin


class Order(Base, TimestampMixin):
    __tablename__ = 'orders'

    __table_args__ = (
        Index('idx_users_id', 'user_id'),
        Index('idx_orders_status', 'status'),
        Index('idx_orders_delivery_status', 'delivery_status'),
        Index('idx_orders_date_created', 'date_created'),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    user_email: Mapped[str] = mapped_column(nullable=False)
    # Exact money: refunds sum these. Was a float column (migration 8d2f6a1c3e57).
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # Breakdown of ``amount``. Null only on orders placed before it existed.
    subtotal_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    shipping_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    # Set when the customer disputes the charge with their bank: "open" until
    # Stripe reports the outcome (won / lost / ...). Flags the order for review.
    dispute_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # The CJ logistics option the customer paid for, and what CJ quoted for it.
    shipping_logistic_name: Mapped[str | None] = mapped_column(nullable=True)
    shipping_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    delivery_status: Mapped[str] = mapped_column(nullable=False)
    payment_intent_id: Mapped[str | None] = mapped_column(unique=True, nullable=True)
    address_id: Mapped[UUID] = mapped_column(ForeignKey('order_addresses.id'), nullable=False)
    cj_order_number: Mapped[str | None] = mapped_column(nullable=True)

    address: Mapped['OrderAddress'] = relationship('OrderAddress', back_populates='orders')
    items: Mapped[list['OrderItem']] = relationship('OrderItem', back_populates='order', cascade="all, delete-orphan")

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
