from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, LargeBinary, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from shared.utils.models_mixins import TimestampMixin


class WebAuthnCredential(Base, TimestampMixin):
    """One passkey an admin registered: what is needed to check its signatures.

    Only public material is stored. The private key never leaves the
    authenticator, so a copy of this table lets nobody sign in.
    """

    __tablename__: str = "webauthn_credentials"

    __table_args__ = (Index("idx_webauthn_credentials_user_id", "user_id"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # The authenticator's own id for the credential; the browser names the
    # passkey it used by it, so it is how a sign-in finds its row.
    credential_id: Mapped[bytes] = mapped_column(LargeBinary, unique=True, nullable=False)
    # COSE-encoded public key, exactly as py_webauthn verifies against it.
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # Authenticators that keep a counter must present a higher one every time;
    # a counter that goes backwards means a cloned authenticator.
    sign_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    transports: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False, default=list)
    aaguid: Mapped[str] = mapped_column(String(36), nullable=False)
    backed_up: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Chosen at enrolment ("MacBook", "YubiKey"), so a lost device can be revoked by name.
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
