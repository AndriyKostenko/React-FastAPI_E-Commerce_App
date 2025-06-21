from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String

from src.models import Base
from src.utils.generate_uuid import generate_uuid

class Notification(Base):
    __tablename__ = 'notifications'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid, unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False)
    message: Mapped[str] = mapped_column(nullable=False)
    is_read: Mapped[bool] = mapped_column(default=False, nullable=False)
    date_created: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc).astimezone(timezone.utc).replace(tzinfo=None),
        nullable=False
    )

    user: Mapped['User'] = relationship('User', back_populates='notifications') 
