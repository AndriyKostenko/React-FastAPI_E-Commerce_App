from uuid import UUID, uuid4
from typing import Any

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Index, inspect
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

from shared.models.models_base_class import Base # type: ignore
from shared.models_mixins import TimestampMixin # type: ignore


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

    @classmethod
    def get_search_fields(cls) -> list[str]:
        """Return list of fields to be used in search operations"""
        return ["name", "email", "phone_number"]

    @classmethod
    def get_admin_schema(cls) -> list[dict[str, Any]]:
        """Get schema information for AdminJS"""
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
        """Map SQLAlchemy types to AdminJS types"""
        type_mapping = {
            'VARCHAR': 'string',
            'TEXT': 'string',
            'INTEGER': 'number',
            'BIGINT': 'number',
            'FLOAT': 'number',
            'BOOLEAN': 'boolean',
            'DATETIME': 'datetime',
            'DATE': 'date',
            'JSON': 'mixed',
            'UUID': 'uuid',
        }

        type_name = sql_type.__class__.__name__.upper()
        return type_mapping.get(type_name, 'string')

    def __repr__(self) -> str:
        return f"User(id={self.id}, name={self.name}, email={self.email}, role={self.role}, is_active={self.is_active}, is_verified={self.is_verified}), date_created={self.date_created}, date_updated={self.date_updated})"
    def __str__(self) -> str:
        return f"User(id={self.id}, name={self.name}, email={self.email}, role={self.role}, is_active={self.is_active}, is_verified={self.is_verified}), date_created={self.date_created}, date_updated={self.date_updated})"
