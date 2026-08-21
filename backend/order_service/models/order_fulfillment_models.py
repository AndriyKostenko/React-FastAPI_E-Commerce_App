from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base
from shared.utils.models_mixins import TimestampMixin


class OrderLineFulfillment(Base, TimestampMixin):
    """Immutable fulfillment and product snapshot for one order item."""

    __tablename__ = "order_line_fulfillments"
    __table_args__ = (
        Index("idx_order_line_fulfillments_order_item", "order_item_id", unique=True),
        Index("idx_order_line_fulfillments_type", "fulfillment_type"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    order_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    fulfillment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    customization: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    variant_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")

    order_item: Mapped["OrderItem"] = relationship(
        "OrderItem", back_populates="fulfillment"
    )


class CustomProductionJob(Base, TimestampMixin):
    """Durable work queue entry for an in-house custom T-shirt line."""

    __tablename__ = "custom_production_jobs"
    __table_args__ = (
        Index("idx_custom_production_order", "order_id"),
        Index("idx_custom_production_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    order_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    specifications: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")


from models.order_item_models import OrderItem  # noqa: E402,F401
