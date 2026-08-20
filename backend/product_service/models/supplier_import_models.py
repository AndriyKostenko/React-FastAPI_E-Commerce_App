from uuid import UUID, uuid4

from sqlalchemy import Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from shared.utils.models_mixins import TimestampMixin


class SupplierImportBatch(Base, TimestampMixin):
    """Durable inbox record for one supplier-products batch."""

    __tablename__ = "supplier_import_batches"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_supplier_import_batch_event_id"),
        UniqueConstraint("supplier_id", "batch_id", name="uq_supplier_import_batch_supplier_batch"),
        Index("idx_supplier_import_batch_fetch_id", "fetch_id"),
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
