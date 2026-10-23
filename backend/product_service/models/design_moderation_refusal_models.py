from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Index, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from infrastructure.database_layer.clipped_string import ClippedString
from infrastructure.utils.models_mixins import TimestampMixin


class DesignModerationRefusal(Base, TimestampMixin):
    """
    A customer design the moderation check refused, kept for the admins.

    One row per refused generation: what was asked for and why it was refused.
    The refused image itself is never stored (nothing was signed, so it cannot
    be ordered either).
    """

    __tablename__ = "design_moderation_refusals"

    __table_args__ = (
        Index("idx_design_moderation_refusals_user", "user_id"),
        CheckConstraint("stage IN ('prompt', 'image')", name="ck_design_moderation_refusals_stage"),
        CheckConstraint(
            "category IN ('sexual', 'hate', 'violence', 'drugs', 'brand', 'character', 'real_person')",
            name="ck_design_moderation_refusals_category",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    # Null only when the job's owner had already expired from Redis.
    user_id: Mapped[UUID | None] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    # As long as GenerateImageRequest allows.
    prompt: Mapped[str] = mapped_column(String(1000), nullable=False)
    style: Mapped[str] = mapped_column(String(100), nullable=False)
    # The model's own words, cut to fit.
    reason: Mapped[str] = mapped_column(ClippedString(500), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    def __repr__(self) -> str:
        return f"DesignModerationRefusal(stage={self.stage}, category={self.category}, user_id={self.user_id})"
