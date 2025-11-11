from uuid import UUID, uuid4

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from shared.models.models_base_class import Base
from shared.models_mixins import TimestampMixin



class Notification(Base, TimestampMixin):
    __tablename__ = 'notifications'
    
    __table_args__ = (
        Index('idx_notification_user_id', 'user_id'),
        Index('idx_notification_date_created', 'date_created'),
        Index('idx_notification_is_read', 'is_read')
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    message: Mapped[str] = mapped_column(nullable=False)
    is_read: Mapped[bool] = mapped_column(default=False, nullable=False)

    user: Mapped['User'] = relationship('User', back_populates='notifications') # type: ignore

    def __repr__(self):
        return f"<Notification(id={self.id}, user_id={self.user_id}, message='{self.message}', is_read={self.is_read})>"
    def __str__(self):
        return f"Notification(id={self.id}, user_id={self.user_id}, message='{self.message}', is_read={self.is_read})"