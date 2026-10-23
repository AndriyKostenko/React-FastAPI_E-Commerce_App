from uuid import UUID

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from infrastructure.utils.models_mixins import TimestampMixin


class GeneratedDesign(Base, TimestampMixin):
    """
    A design the image service stored, and who made it.

    The stored object alone says neither, so this row is what lets the
    retention job delete a design nobody ordered once it is old enough
    (``date_created`` is when it was made), and lets a deleted account's
    unordered designs go with it. Whether it was ordered is read from
    ``retained_artwork``. Designs stored before this table existed have no row
    and are kept.
    """

    __tablename__ = "generated_designs"
    __table_args__ = (
        Index("idx_generated_designs_user", "user_id"),
        Index("idx_generated_designs_created", "date_created"),
    )

    # The object's key in the private bucket (generated-designs/YYYY/MM/<hex>.png).
    key: Mapped[str] = mapped_column(String(512), primary_key=True)
    # Null when the job's owner had already expired from Redis.
    user_id: Mapped[UUID | None] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)

    def __repr__(self) -> str:
        return f"GeneratedDesign(key={self.key}, user_id={self.user_id})"
