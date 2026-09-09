from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from shared.utils.models_mixins import TimestampMixin


class RetainedArtwork(Base, TimestampMixin):
    """A print file that a paid order still depends on.

    product_service owns the stored artwork object but order_service owns the
    reference to it, so nothing local can tell a paid order's print file from
    an abandoned generation draft. This table is that link: a cleanup job that
    sweeps unreferenced drafts must treat any key with an open row here as
    off-limits, however old the object is.
    """

    __tablename__ = "retained_artwork"
    __table_args__ = (
        Index("idx_retained_artwork_key", "artwork_key"),
        Index("idx_retained_artwork_order", "order_id"),
        Index("idx_retained_artwork_released", "released_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    artwork_key: Mapped[str] = mapped_column(String(512), nullable=False)
    order_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    release_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    @property
    def is_active(self) -> bool:
        """True while this hold still protects the object from cleanup."""
        return self.released_at is None
