from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String

from src.models import Base
from src.utils.generate_uuid import generate_uuid

class Shipping(Base):
    __tablename__ = 'shippings'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid, unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False)
    address: Mapped[str] = mapped_column(nullable=False)
    city: Mapped[str] = mapped_column(nullable=False)
    state: Mapped[str] = mapped_column(nullable=False)
    postal_code: Mapped[str] = mapped_column(nullable=False)
    country: Mapped[str] = mapped_column(nullable=False)
    date_created: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc).astimezone(timezone.utc).replace(tzinfo=None),
        nullable=False
    )
    date_updated: Mapped[datetime] = mapped_column(nullable=True)

    user: Mapped['User'] = relationship('User', back_populates='shippings') # type: ignore
