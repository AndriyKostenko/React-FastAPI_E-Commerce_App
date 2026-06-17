from datetime import datetime
from typing import Generic, Optional, TypeVar, Any
from uuid import UUID

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.exceptions.base_exceptions import NoFieldInTheModelError
from shared.models.models_base_class import Base


ModelType = TypeVar("ModelType", bound=Base)


class LockableRepositoryMixin(Generic[ModelType]):
    """Mixin for repositories that need row-level locking via SELECT FOR UPDATE."""

    session: AsyncSession
    model: type[ModelType]

    async def get_by_id_with_lock(self, item_id: UUID) -> ModelType | None:
        """Get a record by ID with a row-level exclusive lock (SELECT FOR UPDATE).

        Use inside an open transaction when you need to read-then-write without
        another concurrent transaction being able to modify the row in between.
        """
        query = (
            select(self.model)
            .where(self.model.id == item_id)
            .with_for_update()
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_many_by_field_with_lock(
        self,
        field_name: str,
        value: str | UUID | bool,
        limit: int = 50,
    ) -> list[ModelType]:
        """Get multiple records by field value with a row-level exclusive lock.

        Uses ``SELECT … FOR UPDATE SKIP LOCKED`` so that concurrent callers
        (e.g. multiple outbox poller workers) each receive a *disjoint* set of
        rows. Rows already locked by another transaction are silently skipped
        rather than causing the query to block or fail.

        Must be called inside an open transaction — the lock is held until the
        transaction commits or rolls back.
        """
        if not hasattr(self.model, field_name):
            raise NoFieldInTheModelError(
                field_name=field_name, model_name=self.model.__name__
            )
        query = (
            select(self.model)
            .where(getattr(self.model, field_name) == value)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


class AdvancedQueryMixin(Generic[ModelType]):
    """Mixin for repositories that need rich filtering, search and ranges."""

    session: AsyncSession
    model: type[ModelType]

    # Subclasses can override this with model-specific fields that must always
    # use equality instead of LIKE when filtered as strings in get_all().
    EQUAL_ONLY_FIELDS: list[str] = ["id", "uuid"]

    async def get_all(
        self,
        filters: dict[str, Any] | None = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = "asc",
        limit: Optional[int] = 50,
        offset: Optional[int] = None,
        date_filters: Optional[dict[str, datetime]] = None,
        search_term: Optional[str] = None,
        search_fields: Optional[list[str]] = None,
        load_relations: Optional[list[str]] = None,
        range_filters: Optional[dict[str, tuple]] = None,
    ) -> list[ModelType]:
        """
        Rich 'get all' query builder with:
        - Dynamic filters (equality or ILIKE for strings)
        - Optional search across multiple fields
        - Range filters (price, quantity, etc.)
        - Date range filters
        - Relationship loading
        - Sorting and pagination
        """
        query = select(self.model)

        # Relationship loading
        if load_relations:
            for relation in load_relations:
                if hasattr(self.model, relation):
                    query = query.options(selectinload(getattr(self.model, relation)))

        # Filters
        if filters:
            for key, value in filters.items():
                if not hasattr(self.model, key):
                    continue
                column = getattr(self.model, key)
                if isinstance(value, str) and key not in self.EQUAL_ONLY_FIELDS:
                    query = query.where(column.ilike(f"%{value}%"))
                else:
                    query = query.where(column == value)

        # Range filters (for price, quantity, etc)
        if range_filters:
            for field_name, (min_value, max_value) in range_filters.items():
                if not hasattr(self.model, field_name):
                    continue
                column = getattr(self.model, field_name)
                if min_value is not None and max_value is not None:
                    query = query.where(column.between(min_value, max_value))
                elif min_value is not None:
                    query = query.where(column >= min_value)
                elif max_value is not None:
                    query = query.where(column <= max_value)

        # Search across multiple fields
        if search_term and search_fields:
            conditions = [
                getattr(self.model, field).ilike(f"%{search_term}%")
                for field in search_fields
                if hasattr(self.model, field)
            ]
            if conditions:
                query = query.where(or_(*conditions))

        # Date range filters
        if date_filters:
            range_map = {
                "date_created": ("date_created_from", "date_created_to"),
                "date_updated": ("date_updated_from", "date_updated_to"),
            }
            for column_name, (from_key, to_key) in range_map.items():
                column = getattr(self.model, column_name, None)
                if column is None:
                    continue
                start = date_filters.get(from_key)
                end = date_filters.get(to_key)
                if start and end:
                    query = query.where(column.between(start, end))
                elif start:
                    query = query.where(column >= start)
                elif end:
                    query = query.where(column <= end)

        # Sorting
        if sort_by and hasattr(self.model, sort_by):
            order_func = asc if sort_order == "asc" else desc
            query = query.order_by(order_func(getattr(self.model, sort_by)))

        # Pagination
        if offset is not None:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())
