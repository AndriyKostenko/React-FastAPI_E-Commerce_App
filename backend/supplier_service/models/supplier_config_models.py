from uuid import UUID, uuid4
from typing import Any

from sqlalchemy import String, Boolean, Integer, JSON, Index, inspect
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.models_base_class import Base
from shared.utils.models_mixins import TimestampMixin


class SupplierConfig(Base, TimestampMixin):
    """Configuration for an external product supplier."""

    __tablename__: str = "supplier_configs"

    __table_args__: tuple = (
        Index("idx_supplier_config_provider_type", "provider_type"),
        Index("idx_supplier_config_is_active", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4, unique=True)
    supplier_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False, default="cjdropshipping")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    default_category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    @classmethod
    def get_search_fields(cls) -> list[str]:
        return ["supplier_id", "name", "provider_type"]

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
