from uuid import UUID
from typing import Generic, Optional, TypeVar, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from shared.exceptions.base_exceptions import NoFieldInTheModelError
from shared.models.models_base_class import Base


# Generic type for SQLAlchemy models
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository for basic CRUD operations.
    Can be used with any SQLAlchemy model.
    """

    def __init__(self, session: AsyncSession, model: type[ModelType]):
        self.session: AsyncSession = session
        self.model: type[ModelType] = model

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
                        item_id: UUID | str | None,
                        load_relations: None | list[str] = None) -> Optional[ModelType]:
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
                      filters: dict[str, Any] | None = None,
                      sort_by: Optional[str] = None,
                      sort_order: Optional[str] = "asc",
                      limit: Optional[int] = 50,
                      offset: Optional[int] = None) -> list[ModelType]:
        """Get all records with optional equality filters, sorting and pagination."""
        query = select(self.model)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)

        if sort_by and hasattr(self.model, sort_by):
            order_clause = getattr(self.model, sort_by).asc() if sort_order == "asc" else getattr(self.model, sort_by).desc()
            query = query.order_by(order_clause)

        if offset is not None:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_field(self, field_name: str, value: str | UUID | bool) -> Optional[ModelType]:
        """Get record by any field"""
        if not hasattr(self.model, field_name):
            raise NoFieldInTheModelError(field_name=field_name, model_name=self.model.__name__)
        result = await self.session.execute(
            select(self.model).where(getattr(self.model, field_name) == value)
        )
        return result.scalar_one_or_none()

    async def get_many_by_field(self, field_name: str, value: str | UUID | bool, limit: int = 50) -> list[ModelType] | None:
        """Get multiple records by field value"""
        if not hasattr(self.model, field_name):
            return None
        result = await self.session.execute(
            select(self.model).where(getattr(self.model, field_name) == value).limit(limit)
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
        query = select(func.count(self.model.id))
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

    async def update_by_field(self, field_name: str, value: str, **kwargs) -> ModelType | None:
        """Update a record by field value with new values"""
        existing_obj = await self.get_by_field(field_name, value)
        if not existing_obj:
            return None
        for field, new_value in kwargs.items():
            if hasattr(existing_obj, field):
                setattr(existing_obj, field, new_value)
        return await self.update(existing_obj)

    async def update_by_id(self, item_id: UUID, data: dict[str, Any]) -> ModelType | None:
        """Update a record by ID with new values"""
        existing_obj = await self.get_by_id(item_id)
        if not existing_obj:
            return None
        for field, value in data.items():
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
