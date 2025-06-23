from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        nullable=False,
    )
    date_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=datetime.now(timezone.utc),
        nullable=True,
    )
