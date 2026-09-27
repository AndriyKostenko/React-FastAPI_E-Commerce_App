from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from shared.contracts.returns import ReturnStatus
from shared.utils.models_mixins import TimestampMixin

# [{"order_item_id": str, "quantity": int, "ships_back": bool, "refunded": bool}]
type ReturnLineRow = dict[str, str | int | bool]
# [{"key": str, "content_type": str, "size": int}]
type ReturnPhotoRow = dict[str, str | int]


class ReturnRequest(Base, TimestampMixin):
    """
    A customer asking to give back delivered units of one order.

    Each line records whether its goods have to come back (the fulfilment
    type's policy decides) and whether it has been refunded yet: returnless
    lines are refunded on approval, the rest when the parcel arrives. A line's
    units stay spoken for while the return is open, so no unit can be returned
    twice; once refunded, the refund row itself keeps them counted.
    """

    __tablename__ = "return_requests"
    __table_args__ = (
        Index("idx_return_requests_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(30), nullable=False)
    fault: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    lines: Mapped[list[ReturnLineRow]] = mapped_column(JSON, nullable=False)
    photos: Mapped[list[ReturnPhotoRow]] = mapped_column(JSON, nullable=False, default=list)
    # Seller's fault: the order's shipping goes back too (once per order).
    refund_shipping: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ReturnStatus.REQUESTED)
    admin_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    decided_by: Mapped[UUID | None] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def return_status(self) -> ReturnStatus:
        return ReturnStatus(self.status)
