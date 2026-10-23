from decimal import Decimal
from typing import List, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, inspect, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from models.base import Base
from infrastructure.utils.models_mixins import TimestampMixin

# Only for the type checker: SQLAlchemy resolves these relationship names
# itself, and importing them at runtime would be circular.
if TYPE_CHECKING:
    from models.order_models import Order


class OrderItem(Base, TimestampMixin):
    __tablename__ = 'order_items'

    __table_args__ = (
        Index('idx_order_items_order_id', 'order_id'),
        Index('idx_order_items_product_id', 'product_id'),
        Index('idx_order_items_variant_id', 'variant_id'),
        # LINE_QUANTITY_MAX (contracts.limits): a line is never merged with another.
        CheckConstraint("quantity BETWEEN 1 AND 99", name="ck_order_items_quantity"),
        CheckConstraint("price > 0", name="ck_order_items_price"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey('orders.id'), nullable=False)
    product_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    variant_id: Mapped[UUID | None] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    quantity: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped['Order'] = relationship('Order', back_populates='items')
    fulfillment: Mapped['OrderLineFulfillment | None'] = relationship(
        'OrderLineFulfillment',
        back_populates='order_item',
        uselist=False,
        cascade="all, delete-orphan",
    )

    @classmethod
    def get_search_fields(cls) -> list[str]:
        """Return list of fields to be used in search operations"""
        return ["order_id", "product_id", "quantity", "price"]

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


from models.order_fulfillment_models import OrderLineFulfillment  # noqa: E402,F401
