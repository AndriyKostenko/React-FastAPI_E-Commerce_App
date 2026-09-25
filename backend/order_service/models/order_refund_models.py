from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from shared.utils.models_mixins import TimestampMixin


class OrderRefund(Base, TimestampMixin):
    """
    Part of an order given back: chosen lines (and quantities), maybe shipping.

    Requested by an admin, or automatically when an unprinted custom line is
    cancelled. Its id travels to payment-service as the Stripe idempotency
    key, so a refund can never be made twice.
    """

    __tablename__ = "order_refunds"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    includes_shipping: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # [{"order_item_id": str, "quantity": int, "amount": str}]
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # The admin who asked; None when the system refunded a cancelled line.
    requested_by: Mapped[UUID | None] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
