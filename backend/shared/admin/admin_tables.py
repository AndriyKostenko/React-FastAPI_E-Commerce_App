"""
Read-only admin listings, declared per table.

The back office (admin-js) needs to page through, filter and open records of
tables that no customer-facing route lists: disputes, CJ orders, shipments,
notifications... Rather than a hand-written list + detail + field-schema route
per table, a service declares each table once::

    AdminTable("disputes", PaymentDispute, DisputeAdminSchema, filterable=("status", "payment_id"))

and ``AdminTableRouter`` builds, behind the admin guard:

    GET /admin/disputes?offset=&limit=&status=...   newest first
    GET /admin/disputes/{id}
    GET /admin/schema/disputes                       field list for AdminJS

The response schema is the single description of what an admin sees: it
shapes the rows and the AdminJS field list alike, so a column left out of it
(a payload, a secret) appears nowhere.
"""

from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from types import NoneType, UnionType
from typing import Annotated, Union, get_args, get_origin
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from shared.auth.route_guards import require_admin

type SessionDependency = Callable[..., AsyncIterator[AsyncSession]]
type FilterValue = str | int | bool | UUID

MAX_PAGE = 100


@dataclass(frozen=True, slots=True)
class AdminTable[ModelT: DeclarativeBase, SchemaT: BaseModel]:
    """One table an admin may browse."""

    # URL segment, e.g. "disputes" -> /admin/disputes.
    name: str
    model: type[ModelT]
    schema: type[SchemaT]
    # Columns an admin may filter on by equality (?status=open).
    filterable: tuple[str, ...] = ()
    # Newest first by this column.
    order_by: str = "date_created"


class AdminFieldSchema:
    """The AdminJS field list for a response schema (path, type, isId)."""

    _TYPES: tuple[tuple[type, str], ...] = (
        (bool, "boolean"),  # before int: bool is an int
        (int, "number"),
        (float, "number"),
        (Decimal, "number"),
        (datetime, "datetime"),  # before date: datetime is a date
        (date, "date"),
        (UUID, "string"),
        (Enum, "string"),
        (str, "string"),
    )

    @classmethod
    def fields(cls, schema: type[BaseModel]) -> list[dict[str, str | bool]]:
        return [
            {"path": name, "type": cls._adminjs_type(field.annotation), "isId": name == "id"}
            for name, field in schema.model_fields.items()
        ]

    @classmethod
    def _adminjs_type(cls, annotation: type | UnionType | None) -> str:
        bare = cls._unwrap(annotation)
        if isinstance(bare, type):
            for python_type, adminjs_type in cls._TYPES:
                if issubclass(bare, python_type):
                    return adminjs_type
        return "string"

    @staticmethod
    def _unwrap(annotation: type | UnionType | None) -> type | UnionType | None:
        """`X | None`, `Optional[X]` and `Annotated[X, ...]` all describe an X."""
        origin = get_origin(annotation)
        if origin is Annotated:
            return AdminFieldSchema._unwrap(get_args(annotation)[0])
        if origin in (Union, UnionType):
            members = [arg for arg in get_args(annotation) if arg is not NoneType]
            return AdminFieldSchema._unwrap(members[0]) if len(members) == 1 else annotation
        return annotation


class AdminTableRouter:
    """Builds the admin-only list, detail and schema routes for a service's tables."""

    def __init__(self, session_dependency: SessionDependency, prefix: str = "/admin") -> None:
        self._session = session_dependency
        self._prefix = prefix

    def build(self, tables: Sequence[AdminTable]) -> APIRouter:
        router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])
        for table in tables:
            self._register(router, table)
        return router

    def _register[ModelT: DeclarativeBase, SchemaT: BaseModel](
        self, router: APIRouter, table: AdminTable[ModelT, SchemaT]
    ) -> None:
        session_dependency = self._session
        primary_key = inspect(table.model).primary_key[0]
        order_column = getattr(table.model, table.order_by)
        columns = {column.key: column for column in inspect(table.model).columns}
        unknown = [name for name in table.filterable if name not in columns]
        if unknown:
            raise ValueError(f"{table.name}: cannot filter on unknown columns {unknown}")

        async def list_rows(
            request: Request,
            session: AsyncSession = Depends(session_dependency, scope="function"),
            offset: int = Query(0, ge=0),
            limit: int = Query(25, ge=1, le=MAX_PAGE),
        ) -> list[SchemaT]:
            query = select(table.model)
            # Only declared columns filter; anything else in the query string
            # is ignored rather than turned into SQL.
            for name in table.filterable:
                raw = request.query_params.get(name)
                if raw in (None, ""):
                    continue
                try:
                    value = self._coerce(columns[name].type.python_type, raw)
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Invalid value for {name}"
                    )
                query = query.where(columns[name] == value)
            query = query.order_by(order_column.desc()).offset(offset).limit(limit)
            rows = (await session.execute(query)).scalars().all()
            return [table.schema.model_validate(row, from_attributes=True) for row in rows]

        async def get_row(
            record_id: str,
            session: AsyncSession = Depends(session_dependency, scope="function"),
        ) -> SchemaT:
            try:
                key = self._coerce(primary_key.type.python_type, record_id)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No such {table.name} record")
            row = await session.get(table.model, key)
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No such {table.name} record")
            return table.schema.model_validate(row, from_attributes=True)

        async def get_schema() -> dict[str, list[dict[str, str | bool]]]:
            return {"fields": AdminFieldSchema.fields(table.schema)}

        path = f"{self._prefix}/{table.name}"
        router.add_api_route(path, list_rows, methods=["GET"], response_model=list[table.schema],
                             summary=f"List {table.name} (admin)", name=f"admin_list_{table.name}")
        router.add_api_route(f"{self._prefix}/schema/{table.name}", get_schema, methods=["GET"],
                             summary=f"AdminJS fields of {table.name}", name=f"admin_schema_{table.name}")
        router.add_api_route(f"{path}/{{record_id}}", get_row, methods=["GET"], response_model=table.schema,
                             summary=f"One {table.name} record (admin)", name=f"admin_get_{table.name}")

    @staticmethod
    def _coerce(python_type: type, raw: str) -> FilterValue:
        if python_type is UUID:
            return UUID(raw)
        if python_type is bool:
            if raw.lower() not in ("true", "false"):
                raise ValueError(f"not a boolean: {raw}")
            return raw.lower() == "true"
        if python_type is int:
            return int(raw)
        return raw
