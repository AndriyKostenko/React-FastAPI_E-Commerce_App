from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from infrastructure.utils.models_mixins import TimestampMixin


class SupplierImportBatch(Base, TimestampMixin):
    """Durable inbox record for one supplier-products batch."""

    __tablename__ = "supplier_import_batches"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_supplier_import_batch_event_id"),
        UniqueConstraint("supplier_id", "batch_id", name="uq_supplier_import_batch_supplier_batch"),
        Index("idx_supplier_import_batch_fetch_id", "fetch_id"),
        CheckConstraint(
            "batch_number >= 1 AND total_batches >= 1 AND imported >= 0 AND updated >= 0 AND failed >= 0",
            name="ck_supplier_import_batches_counts",
        ),
        # BATCH_MAX (contracts.limits): one error at most per product of the batch.
        CheckConstraint("jsonb_array_length(errors) <= 1000", name="ck_supplier_import_batches_errors"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(100), nullable=False)
    fetch_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    batch_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    batch_number: Mapped[int] = mapped_column(Integer, nullable=False)
    total_batches: Mapped[int] = mapped_column(Integer, nullable=False)
    imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
