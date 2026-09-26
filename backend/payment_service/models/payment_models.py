from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Index, inspect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from models.base import Base
from shared.utils.models_mixins import TimestampMixin


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    __table_args__ = (
        Index("idx_payments_order_id", "order_id"),
        Index("idx_payments_status", "status"),
        Index("idx_payments_stripe_payment_intent_id", "stripe_payment_intent_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    user_email: Mapped[str] = mapped_column(nullable=False)
    stripe_payment_intent_id: Mapped[str] = mapped_column(unique=True, nullable=False)
    amount: Mapped[int] = mapped_column(nullable=False)  # stored in cents (e.g. $9.99 → 999)
    currency: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    failure_reason: Mapped[str] = mapped_column(nullable=True)
    # Partial refunds (cents). refunded_cents went back after capture;
    # capture_reduction_cents was taken off before capture, so the card is
    # simply charged less. Both are bounded by ``amount``.
    refunded_cents: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    capture_reduction_cents: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    # Stripe Tax: the calculation the order was priced with, and the sale
    # transaction recorded from it once the card was captured.
    tax_calculation_id: Mapped[str | None] = mapped_column(nullable=True)
    tax_transaction_id: Mapped[str | None] = mapped_column(nullable=True)

    @property
    def refundable_cents(self) -> int:
        return self.amount - self.refunded_cents - self.capture_reduction_cents

    @classmethod
    def get_search_fields(cls) -> list[str]:
        return ["status", "stripe_payment_intent_id", "order_id"]

    @classmethod
    def get_admin_schema(cls) -> list[dict[str, str]]:
        inspector = inspect(cls)
        fields = []
        for column in inspector.columns:
            field_info = {
                "path": column.name,
                "type": cls._map_sqlalchemy_type_to_adminjs(column.type),
                "isId": column.primary_key,
            }
            fields.append(field_info)
        return fields

    @staticmethod
    def _map_sqlalchemy_type_to_adminjs(sql_type) -> str:
        type_mapping = {
            "VARCHAR": "string",
            "TEXT": "string",
            "INTEGER": "number",
            "BIGINT": "number",
            "FLOAT": "number",
            "BOOLEAN": "boolean",
            "DATETIME": "datetime",
            "DATE": "date",
            "JSON": "mixed",
            "UUID": "uuid",
        }
        type_name = sql_type.__class__.__name__.upper()
        return type_mapping.get(type_name, "string")


class PaymentRefund(Base, TimestampMixin):
    """
    One partial refund order_service asked for. Its id is order_service's
    refund id, so a redelivered command finds the row and changes nothing.
    """

    __tablename__ = "payment_refunds"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    payment_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("payments.id"), nullable=False, index=True
    )
    amount_cents: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(nullable=False)
    # succeeded: refunded on Stripe; reduced_capture: taken off before capture;
    # failed: refused (over the refundable amount, payment not refundable).
    status: Mapped[str] = mapped_column(nullable=False)
    stripe_refund_id: Mapped[str | None] = mapped_column(nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(nullable=True)


class PaymentDispute(Base, TimestampMixin):
    """A chargeback on one payment, as Stripe reports it. Keyed by Stripe's id."""

    __tablename__ = "payment_disputes"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    stripe_dispute_id: Mapped[str] = mapped_column(unique=True, nullable=False)
    # Null when Stripe reports a dispute on a charge this service has no record of.
    payment_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("payments.id"), nullable=True, index=True
    )
    amount_cents: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    evidence_due_by: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
