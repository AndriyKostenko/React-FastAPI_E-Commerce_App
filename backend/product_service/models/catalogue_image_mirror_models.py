from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from shared.utils.models_mixins import TimestampMixin


class MirrorStatus(StrEnum):
    PENDING = "pending"    # seen, not yet copied (or a copy failed and will be retried)
    MIRRORED = "mirrored"  # copied; object_key names it in the catalogue store
    FAILED = "failed"      # gave up; the source URL keeps being served


class CatalogueImageMirror(Base, TimestampMixin):
    """A supplier image copied into the catalogue store.

    One row per source URL, shared by every product, gallery image and variant
    that uses it. Once mirrored, the supplier sync writes ``object_key`` in
    place of the URL (``CatalogueImageMirrorRepository.mirrored_keys``), so a
    re-sync never puts the supplier's link back.
    """

    __tablename__ = "catalogue_image_mirrors"
    __table_args__ = (
        Index("idx_catalogue_image_mirrors_source_url", "source_url", unique=True),
        Index("idx_catalogue_image_mirrors_status", "status"),
        CheckConstraint(
            "status IN ('pending', 'mirrored', 'failed')",
            name="ck_catalogue_image_mirrors_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=MirrorStatus.PENDING)
    object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mirrored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
