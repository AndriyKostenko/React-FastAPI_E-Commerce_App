from datetime import datetime
from uuid import UUID
from typing import Set

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all models in the product service.
    Inherits from SQLAlchemy's DeclarativeBase to provide ORM capabilities.
    """
    # Default fields to exclude for all models
    default_exclude: Set[str] = set()
    
    def to_dict(self, exclude: Set[str] = None) -> dict:
        """Convert model instance to dictionary for caching serizlization"""
        all_excludes = self.default_exclude | (exclude or set())
        data = {}
        for key, value in self.__dict__.items():
            if not key.startswith("_") and key not in all_excludes: # skip SQLAlchemy attributes and exlude fields
                if isinstance(value, datetime):
                    data[key] = value.isoformat()
                elif isinstance(value, UUID):
                    data[key] = str(value)
                else:
                    data[key] = value
        return data