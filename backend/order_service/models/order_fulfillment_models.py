from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base
from shared.contracts.artwork import GeneratedArtworkAsset
from shared.enums.status_enums import LineFulfillmentStatus, ProductionJobStatus
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
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=LineFulfillmentStatus.PENDING
    )

    order_item: Mapped["OrderItem"] = relationship(
        "OrderItem", back_populates="fulfillment"
    )

    @property
    def is_dispatched(self) -> bool:
        """True once this line's goods have physically left."""
        return self.status in LineFulfillmentStatus.dispatched()

    @property
    def blocks_cancellation(self) -> bool:
        """True when cancelling this line would refund goods already spent or sent."""
        return self.status in LineFulfillmentStatus.blocks_cancellation()


class CustomProductionJob(Base, TimestampMixin):
    """Durable work queue entry for an in-house custom T-shirt line.

    This is the operator's unit of work: one row is one garment order to
    print, pack, and post. The row carries the whole lifecycle rather than a
    bare status, because the tracking number entered at dispatch and the
    timestamps of each step are what the customer notification and any later
    return decision are built from.
    """

    __tablename__ = "custom_production_jobs"
    __table_args__ = (
        Index("idx_custom_production_order", "order_id"),
        Index("idx_custom_production_status", "status"),
        Index("idx_custom_production_reconciliation", "reconciliation_required"),
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
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=ProductionJobStatus.QUEUED
    )

    # Dispatch details entered by the operator when the parcel is posted.
    tracking_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    carrier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tracking_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Free-form workshop notes (blank stock used, reprint reason, ...).
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    printed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    shipped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Set when the job was cancelled after materials were already spent or the
    # parcel was already posted, so a human decides on return and refund.
    reconciliation_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    order: Mapped["Order"] = relationship("Order")
    order_item: Mapped["OrderItem"] = relationship("OrderItem")

    @property
    def job_status(self) -> ProductionJobStatus:
        return ProductionJobStatus(self.status)

    @property
    def artwork_asset(self) -> GeneratedArtworkAsset | None:
        """The signed print-file manifest captured when the order was priced.

        Returns ``None`` for a legacy or hand-made job whose specifications
        never carried a generated design.
        """
        asset = (self.specifications or {}).get("design_asset")
        if not asset:
            return None
        return GeneratedArtworkAsset(**asset)


from models.order_item_models import OrderItem  # noqa: E402,F401
from models.order_models import Order  # noqa: E402,F401
