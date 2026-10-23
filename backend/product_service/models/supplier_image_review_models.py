from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from infrastructure.database_layer.clipped_string import ClippedString
from infrastructure.utils.models_mixins import TimestampMixin


class SupplierImageReview(Base, TimestampMixin):
    """
    A vision model's verdict on one supplier product photo, kept for good.

    One row per (supplier, product, photo URL): a photo is reviewed once, so a
    rejected one is not paid for again every sync and an approved one's
    description is reused instead of being overwritten by the supplier's.
    A new main photo from the supplier gets a row of its own. The rows are
    also the record of why a product was or was not imported.
    """

    __tablename__ = "supplier_image_reviews"

    __table_args__ = (
        UniqueConstraint("supplier_id", "pid", "image_url", name="uq_supplier_image_reviews_photo"),
        Index("idx_supplier_image_reviews_product", "supplier_id", "pid"),
        CheckConstraint("verdict IN ('approved', 'rejected')", name="ck_supplier_image_reviews_verdict"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    supplier_id: Mapped[str] = mapped_column(String(255), nullable=False)
    pid: Mapped[str] = mapped_column(String(255), nullable=False)
    # The supplier's URL of the photo reviewed (never the catalogue copy's key).
    image_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(ClippedString(500), nullable=False)
    # The description written from the photo; only on approved rows.
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    def __repr__(self) -> str:
        return f"SupplierImageReview(pid={self.pid}, verdict={self.verdict}, model={self.model})"
