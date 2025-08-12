from uuid import UUID, uuid4

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Index
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from shared.models_base_class import Base
from shared.models_mixins import TimestampMixin


# User model representing a user in the system
class User(Base, TimestampMixin):
    __tablename__ = 'users'
    
    # Creating indexes for the columns
    # to improve query performance, applied to often queried fields
    __table_args__ = (
        Index('idx_users_email', 'email'),
        Index('idx_users_role', 'role'),
        Index('idx_users_is_active', 'is_active'),
        Index('idx_users_is_verified', 'is_verified'),
        Index('idx_users_date_created', 'date_created'),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True)
    name: Mapped[str] = mapped_column(String(50),nullable=False)
    email: Mapped[str] = mapped_column(String(100),unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(nullable=True)
    phone_number: Mapped[str] = mapped_column(nullable=True)
    image: Mapped[str] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    
    
    def __repr__(self) -> str:
        return f"User(id={self.id}, name={self.name}, email={self.email}, role={self.role}, is_active={self.is_active}, is_verified={self.is_verified}), date_created={self.date_created}, date_updated={self.date_updated})"
    def __str__(self) -> str:
        return f"User(id={self.id}, name={self.name}, email={self.email}, role={self.role}, is_active={self.is_active}, is_verified={self.is_verified}), date_created={self.date_created}, date_updated={self.date_updated})"
