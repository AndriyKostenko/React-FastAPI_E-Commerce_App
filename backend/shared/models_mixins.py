from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(), # Database-level default
        nullable=False,
    )
    date_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(), # Database-level update trigger
        nullable=True,
    )
