from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import String, Integer, DateTime, Text, Index, ForeignKey, inspect
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.models_base_class import Base
from shared.utils.models_mixins import TimestampMixin


class SupplierSyncState(Base, TimestampMixin):
    """Tracks the last successful sync run for each supplier."""

    __tablename__: str = "supplier_sync_states"

    __table_args__: tuple = (
        Index("idx_supplier_sync_state_supplier_id", "supplier_id"),
        Index("idx_supplier_sync_state_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True)
    supplier_id: Mapped[str] = mapped_column(String(100), ForeignKey("supplier_configs.supplier_id"), nullable=False)
    fetch_id: Mapped[UUID | None] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    products_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_emitted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    @classmethod
    def get_search_fields(cls) -> list[str]:
        return ["supplier_id", "status"]

    @classmethod
    def get_admin_schema(cls) -> list[dict[str, str]]:
        inspector = inspect(cls)
        fields = []
        type_mapping = {
            "VARCHAR": "string",
            "TEXT": "string",
            "INTEGER": "number",
            "BIGINT": "number",
            "FLOAT": "number",
            "NUMERIC": "number",
            "DECIMAL": "number",
            "BOOLEAN": "boolean",
            "DATETIME": "datetime",
            "DATE": "date",
            "JSON": "mixed",
            "UUID": "uuid",
        }
        for column in inspector.columns:
            fields.append({
                "path": column.name,
                "type": type_mapping.get(column.type.__class__.__name__.upper(), "string"),
                "isId": column.primary_key,
            })
        return fields
