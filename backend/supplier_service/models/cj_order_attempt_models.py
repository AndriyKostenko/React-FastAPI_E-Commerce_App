from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Index, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from shared.utils.models_mixins import TimestampMixin


class CJOrderAttempt(Base, TimestampMixin):
    """Durable local record of the non-transactional CJ order boundary."""

    __tablename__ = "cj_order_attempts"
    __table_args__ = (Index("idx_cj_order_attempt_status", "status"),)

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    order_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=False, unique=True
    )
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    cj_order_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)

