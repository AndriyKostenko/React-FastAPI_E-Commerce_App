from uuid import UUID, uuid4
from sqlalchemy import Index, inspect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from shared.models.models_base_class import Base
from shared.utils.models_mixins import TimestampMixin


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    __table_args__ = (
        Index("idx_payments_order_id", "order_id"),
        Index("idx_payments_status", "status"),
        Index("idx_payments_stripe_payment_intent_id", "stripe_payment_intent_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True)
    order_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    user_email: Mapped[str] = mapped_column(nullable=False)
    stripe_payment_intent_id: Mapped[str] = mapped_column(unique=True, nullable=False)
    amount: Mapped[int] = mapped_column(nullable=False)  # stored in cents (e.g. $9.99 → 999)
    currency: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    failure_reason: Mapped[str] = mapped_column(nullable=True)

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
