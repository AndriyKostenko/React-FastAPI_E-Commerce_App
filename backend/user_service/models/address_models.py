from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from infrastructure.utils.models_mixins import TimestampMixin


class UserAddress(Base, TimestampMixin):
    """A shipping address a customer saved for later checkouts.

    The same shape as an order's address, so checkout can hand it to
    order-service unchanged. Only Canadian addresses are stored (the store
    ships nowhere else), already normalised: province as its two-letter code,
    postal code as ``A1A 1A1``.
    """

    __tablename__: str = "user_addresses"

    __table_args__ = (
        Index("idx_user_addresses_user_id", "user_id"),
        # At most one default per user, enforced by the database: two
        # concurrent "make default" calls cannot both win.
        Index(
            "uq_user_addresses_one_default",
            "user_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # What the customer calls it ("Home", "Work").
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    # The recipient, as the carrier prints it.
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    street: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    province: Mapped[str] = mapped_column(String(2), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(7), nullable=False)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
