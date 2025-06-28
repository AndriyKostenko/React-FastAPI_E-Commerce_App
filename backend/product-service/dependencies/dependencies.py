import re
from typing import Annotated, AsyncGenerator

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
    
    1.Client sends HTTP request.
    2.FastAPI receives and resolves dependencies for the endpoint.
    3.get_db_session is called as a dependency, which:
     -Calls DatabaseSessionManager.session() (an async context manager).
     -This opens a new AsyncSession for this request.
    4.get_db_session yields this session to the dependency tree.
    5.UserCRUDService receives the session via dependency injection.
    6.Service methods use the session to talk to the DB.
    7.Data flows back up to the FastAPI endpoint, which serializes the result and returns it to the Client.
    8.After the response (or on error), the AsyncSession context manager exits and closes/cleans up.
"""


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Providing a transactional scope around for each series (request) of operations with database."""
    async with database_session_manager.session() as session:
        yield session
        

def get_product_service(session: AsyncSession = Depends(get_db_session)) -> ProductCRUDService:
    """Provides an instance of ProductCRUDService."""
    return ProductCRUDService(session=session)


def get_category_service(session: AsyncSession = Depends(get_db_session)) -> CategoryCRUDService:
    """Provides an instance of CategoryCRUDService."""
    return CategoryCRUDService(session=session)


def get_review_service(session: AsyncSession = Depends(get_db_session)) -> ReviewCRUDService:
    """Provides an instance of ReviewCRUDService."""
    return ReviewCRUDService(session=session)
        
    
product_crud_dependency = Annotated[ProductCRUDService, Depends(get_product_service)]
category_crud_dependency = Annotated[CategoryCRUDService, Depends(get_category_service)]
review_crud_dependency = Annotated[ReviewCRUDService, Depends(get_review_service)]
