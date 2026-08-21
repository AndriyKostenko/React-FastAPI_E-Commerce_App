from uuid import UUID, uuid4

from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from shared.utils.models_mixins import TimestampMixin


class InventoryReservation(Base, TimestampMixin):
    """Durable idempotency ledger for inventory reservation and release."""

    __tablename__ = "inventory_reservations"
    __table_args__ = (
        UniqueConstraint("order_id", "line_key", name="uq_inventory_order_line"),
        Index("idx_inventory_reservation_order", "order_id"),
        Index("idx_inventory_reservation_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    order_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    product_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    variant_id: Mapped[UUID | None] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    line_key: Mapped[str] = mapped_column(String(80), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="reserved")
