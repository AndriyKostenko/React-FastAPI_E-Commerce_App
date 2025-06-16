import re
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from services.product_service import ProductCRUDService
from services.category_service import CategoryCRUDService
from services.review_service import ReviewCRUDService
from database import database_session_manager



"""
FLow Diagram for Database Session Management in FastAPI:

    A[HTTP Request] --> B[FastAPI Router]
    B --> C[get_db_session Dependency]
    C --> D[DatabaseSessionManager.session]
    D --> E[Database Operations]
    E --> F[Commit/Rollback]
    F --> G[Session Cleanup]
    G --> H[HTTP Response]
"""


# dependency that will be used to get the database session from the request
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Providing a transactional scope around for each series (request) of operations with database."""
    async with database_session_manager.session() as session:
        yield session
        

def get_product_service(session: AsyncSession = Depends(get_db_session)) -> ProductCRUDService:
    """Provides an instance of ProductCRUDService."""
    return ProductCRUDService(session=session)

@staticmethod
def get_category_service(session: AsyncSession = Depends(get_db_session)) -> CategoryCRUDService:
    """Provides an instance of CategoryCRUDService."""
    return CategoryCRUDService(session=session)

@staticmethod
def get_review_service(session: AsyncSession = Depends(get_db_session)) -> ReviewCRUDService:
    """Provides an instance of ReviewCRUDService."""
    return ReviewCRUDService(session=session)
        
    


