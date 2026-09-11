from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from shared.utils.models_mixins import TimestampMixin


class CJOrderAttempt(Base, TimestampMixin):
    """Durable local record of the non-transactional CJ order boundary.

    After creation the row doubles as the tracking state for that CJ order:
    the poller advances ``status`` through shipped/delivered and records the
    carrier data the customer is notified with.
    """

    __tablename__ = "cj_order_attempts"
    __table_args__ = (
        Index("idx_cj_order_attempt_status", "status"),
        # Drives the tracking poller's "oldest open orders first" scan.
        Index("idx_cj_order_attempt_poll", "status", "last_polled_at"),
        # Drives the payment retry task's scan of unpaid orders.
        Index("idx_cj_order_attempt_payment_due", "status", "date_updated"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    order_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=False, unique=True
    )
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    # Captured at creation so the tracking poller can emit customer-facing
    # events without calling back into order_service.
    user_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    cj_order_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cj_order_status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    logistic_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_polled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # What CJ billed, and the most it may bill before payment is held for
    # review: expected product cost plus quoted freight, with tolerance.
    cj_order_amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    expected_max_amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
