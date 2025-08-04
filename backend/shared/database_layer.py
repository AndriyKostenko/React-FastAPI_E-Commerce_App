from uuid import UUID
from typing import Generic, Optional, Type, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc
from pydantic import EmailStr
from shared.base_exceptions import NoFieldInTheModelError
from shared.models_base_class import Base

# Generic type for SQLAlchemy models
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    A database service layer.
    Generic repository for CRUD operations.
    Can be used with any SQLAlchemy model.
    """

    def __init__(self, session: AsyncSession, model: Type[ModelType]):
        self.session = session
        self.model = model

    # CREATE
    async def create(self, obj: ModelType) -> ModelType:
        """Creating a new record"""
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj
    
    async def create_many(self, objects: list[ModelType]) -> list[ModelType]:
        """Create multiply records"""
        self.session.add_all(objects)
        await self.session.commit()
        for obj in objects:
            await self.session.refresh(obj)
        return objects
    
    # READ
    async def get_by_id(self, id: UUID) -> Optional[ModelType]:
        """Get a record by ID"""
        result = await self.session.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()
    
    async def get_all(self,
                      limit: Optional[int] = None,
                      offset: Optional[int] = None,
                      order_by: Optional[str] = None) -> list[ModelType]:
        """Get all records with optional limit, offset, and order by"""
        query = select(self.model)
        if order_by:
            if hasattr(self.model, order_by):
                query = query.order_by(asc(getattr(self.model, order_by)))        
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
        
    async def get_by_field(self, field_name: str, value: str) -> Optional[ModelType]:
        """Get record by any field"""
        if not hasattr(self.model, field_name):
            raise NoFieldInTheModelError(self.model.__name__, field_name)

        
        result = await self.session.execute(
            select(self.model).where(getattr(self.model, field_name) == value)
        )
        
        return result.scalar_one_or_none()
        
    async def get_many_by_field(self, field_name: str, value: str) -> list[Optional[ModelType]]:
        """Get multiple records by field value"""
        if not hasattr(self.model, field_name):
            raise AttributeError(f"Model {self.model.__name__} has no field '{field_name}'")
        
        result = await self.session.execute(
            select(self.model).where(getattr(self.model, field_name) == value)
        )
        return result.scalars().all()
    
    async def filter_by(self, **kwargs) -> list[ModelType]:
        """Filter records by multiply fields"""
        query = select(self.model)
        for field, value in kwargs.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)
        
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count(self, **kwargs) -> int:
        """Count records with optional filters"""
        query = select(self.model)
        for field, value in kwargs.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)
        
        result = await self.session.execute(query)
        return result.scalar() if result else 0
    
    # UPDATE
    async def update(self, obj: ModelType) -> ModelType:
        """Update an existing record"""
        self.session.add(obj)
        await self.session.commit()
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
    
    async def update_by_id(self, id: UUID, **kwargs) -> Optional[ModelType]:
        """Update a record by ID with new values"""
        existing_obj = await self.get_by_id(id)
        if not existing_obj:
            return None
        for field, value in kwargs.items():
            if hasattr(existing_obj, field):
                setattr(existing_obj, field, value)
        return await self.update(existing_obj)
    
    async def update_by_email(self, email: EmailStr, **kwargs) -> Optional[ModelType]:
        existing_obj = await self.get_by_field(field_name="email", value=email)
        if not existing_obj:
            return None
        for field, value in kwargs.items():
            if hasattr(existing_obj, field):
                setattr(existing_obj, field, value)
        return await self.update(existing_obj)
        
    
    # DELETE
    async def delete(self, obj: ModelType) -> None:
        """Delete a record"""
        await self.session.delete(obj)
        await self.session.commit()

    async def delete_by_id(self, id: UUID) -> bool:
        """Delete a record by ID"""
        existing_obj = await self.get_by_id(id)
        if existing_obj:
            await self.delete(existing_obj)
            return True
        return False
    
    async def delete_many_by_field(self, field_name: str, value: str) -> int:
        """Delete multiple records by field value"""
        if hasattr(self.model, field_name):
            result = await self.session.execute(
                select(self.model).where(getattr(self.model, field_name) == value)
            )
            objects_to_delete = result.scalars().all()
            for obj in objects_to_delete:
                await self.session.delete(obj)
            await self.session.commit()
            return len(objects_to_delete)
        return 0
    
    async def delete_many(self, objects: list[ModelType]) -> int:
        """Delete multiple records"""
        for obj in objects:
            await self.session.delete(obj)
        await self.session.commit()
        return len(objects)
    
    