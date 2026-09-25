from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from shared.utils.models_mixins import TimestampMixin


class OrderSagaState(Base, TimestampMixin):
    """Durable gate state for payment, inventory, and fulfillment."""

    __tablename__ = "order_saga_states"

    order_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        primary_key=True,
    )
    inventory_status: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending"
    )
    fulfillment_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending"
    )
    cancellation_reason: Mapped[str | None] = mapped_column(nullable=True)
    # When payment and inventory both cleared. The stalled-supplier sweep
    # measures from here; date_updated moves with every later change.
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(nullable=False, default=0)
