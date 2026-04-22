from datetime import datetime
from uuid import UUID, uuid4
from typing import Any

from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON
from sqlalchemy import DateTime, inspect, Index

from shared.models.models_base_class import Base
from shared.utils.models_mixins import TimestampMixin


class OutboxEvent(Base, TimestampMixin):
    __tablename__: str = "payment_outbox_events"
    __table_args__: tuple[Index, ...] = (
        Index('idx_outbox_events_event_type', 'event_type'),
        Index('idx_outbox_events_processed', 'processed'),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True)
    event_type: Mapped[str] = mapped_column(nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    processed: Mapped[bool] = mapped_column(default=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    @classmethod
    def get_search_fields(cls) -> list[str]:
        return ["event_type", "payload", "processed", "processed_at"]

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
