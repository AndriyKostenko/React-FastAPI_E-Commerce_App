from datetime import datetime
from uuid import UUID
from typing import Generic, Optional, Type, TypeVar, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, asc, desc, or_
from sqlalchemy.orm import selectinload, InstrumentedAttribute

from shared.base_exceptions import NoFieldInTheModelError
from shared.models.models_base_class import Base


# Generic type for SQLAlchemy models
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    A database service layer.
    Generic repository for CRUD operations.
    Can be used with any SQLAlchemy model.
    """
    # list of fields that must always use equality, even if string type
    EQUAL_ONLY_FIELDS = ["sku", "id", "uuid", "email", "phone_number"]

    def __init__(self, session: AsyncSession, model: Type[ModelType]):
        self.session = session
        self.model = model

    # ---------------- CREATE ----------------
    async def create(self, obj: ModelType) -> ModelType:
        """Creating a new record"""
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def create_many(self, objects: list[ModelType]) -> list[ModelType]:
        """Create multiply records"""
        self.session.add_all(objects)
        await self.session.flush()
        for obj in objects:
            await self.session.refresh(obj)
        return objects

    # ---------------- READ ----------------
    async def get_by_id(self,
                        item_id: UUID,
                        load_relations: Optional[list[str]] = None) -> Optional[ModelType]:
        """Get a record by ID"""
        query = select(self.model)
        if load_relations:
            for relation in load_relations:
                if hasattr(self.model, relation):
                    query = query.options(selectinload(getattr(self.model, relation)))
        query = query.where(self.model.id == item_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(self,
                      filters: Optional[dict[str, Any]] = None,
                      sort_by: Optional[str] = None,
                      sort_order: Optional[str] = "asc",
                      limit: Optional[int] = 50,
                      offset: Optional[int] = None,
                      date_filters: Optional[dict[str, datetime]] = None,
                      search_term: Optional[str] = None,
                      search_fields: Optional[list[str]] = None,
                      load_relations: Optional[list[str]] = None,
                      range_filters: Optional[dict[str, tuple]] = None) -> list[ModelType]:
        """
        Universal 'get all' method with:
        - Dynamic filters
        - Optional search (on multiple fields)
        - Sorting, pagination
        - Relationship loading
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
                # Determine if equality or LIKE should be used
                column: InstrumentedAttribute = getattr(self.model, key)
                if isinstance(value, str) and key not in self.EQUAL_ONLY_FIELDS:
                    # Use case-insensitive LIKE for string fields (except those in EQUAL_ONLY_FIELDS)
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

        # Search across multiply fields
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
                "date_updated": ("date_updated_from", "date_updated_to")
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
        print("Executed query:", str(query))
        return list(result.scalars().all())

    async def get_by_field(self, field_name: str, value: str | UUID) -> Optional[ModelType]:
        """Get record by any field"""
        if not hasattr(self.model, field_name):
            raise NoFieldInTheModelError(field_name=field_name, model_name=self.model.__name__)
        result = await self.session.execute(
            select(self.model).where(getattr(self.model, field_name) == value)
        )
        return result.scalar_one_or_none()

    async def get_many_by_field(self, field_name: str, value: str | UUID) -> list[Optional[ModelType]]:
        """Get multiple records by field value"""
        if not hasattr(self.model, field_name):
            return []
        result = await self.session.execute(
            select(self.model).where(getattr(self.model, field_name) == value)
        )
        return list(result.scalars().all())

    async def filter_by(self, **kwargs) -> list[ModelType]:
        """Filter records by multiply fields"""
        query = select(self.model)  # Always initialize query
        for field, value in kwargs.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count(self, **kwargs) -> int:
        """Count records with optional filters"""
        # counting by primary key (id) as default
        query = select(func.count(self.model.id))  # type: ignore
        for field, value in kwargs.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)

        result = await self.session.execute(query)
        return result.scalar() or 0

    # ---------------- UPDATE ----------------
    async def update(self, obj: ModelType) -> ModelType:
        """Update an existing record"""
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update_by_field(self, field_name: str, value: str, **kwargs) -> Optional[ModelType]:
        """Update a record by field value with new values"""
        existing_obj = await self.get_by_field(field_name, value)
        if not existing_obj:
            return None
        for field, new_value in kwargs.items():
            if hasattr(existing_obj, field):
                setattr(existing_obj, field, new_value)
        return await self.update(existing_obj)

    async def update_by_id(self, item_id: UUID, **kwargs) -> Optional[ModelType]:
        """Update a record by ID with new values"""
        existing_obj = await self.get_by_id(item_id)
        if not existing_obj:
            return None
        for field, value in kwargs.items():
            if hasattr(existing_obj, field):
                setattr(existing_obj, field, value)
        return await self.update(existing_obj)


    #  ---------------- DELETE ----------------
    async def delete(self, obj: ModelType) -> None:
        """Delete a record"""
        await self.session.delete(obj)

    async def delete_by_id(self, item_id: UUID) -> bool:
        """Delete a record by ID"""
        existing_obj = await self.get_by_id(item_id)
        if existing_obj:
            await self.delete(existing_obj)
            return True
        return False

    async def delete_many_by_field(self, field_name: str, value: str | UUID) -> None:
        """Delete multiple records by field value"""
        objects_to_delete = await self.get_many_by_field(field_name, value)
        if objects_to_delete:
            for obj in objects_to_delete:
                await self.session.delete(obj)

    async def delete_many(self, objects: list[ModelType]) -> None:
        """Delete multiple records"""
        for obj in objects:
            await self.session.delete(obj)
