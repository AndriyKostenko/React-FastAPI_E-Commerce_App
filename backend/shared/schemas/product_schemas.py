from typing import Optional

from pydantic import BaseModel, Field


class BaseFilters(BaseModel):
    # Pagination
    offset: int = Field(default=0, ge=0, description="Number of records to skip")
    limit: int = Field(default=10, gt=0, le=100, description="Maximum number of records to return")
    
    # Sorting
    sort_order: Optional[str] = Field(None, pattern="^(asc|desc)$")