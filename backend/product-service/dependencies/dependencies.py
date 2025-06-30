import re
from typing import Annotated, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from services.product_service import ProductService
from services.category_service import CategoryService
from services.review_service import ReviewService
from repositories.product_repository import ProductRepository
from repositories.category_repository import CategoryRepository
from repositories.review_repository import ReviewRepository
from db.database import database_session_manager



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
    5.ProductService, CategoryService, ReviewServcie are receiving the repository for managing db operation with the session via dependency injection.
    6.Service methods use the *Repository  to talk to the DB.
    7.Data flows back up to the *Service , which serializes the result and returns it to the Client.
    8.Then data flows to FastAPI edpoints which cache / rate-limit / additionaly validate the response via response_model
"""


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Providing a transactional scope around for each series (request) of operations with database."""
    async with database_session_manager.session() as session:
        yield session
        

def get_product_service(session: AsyncSession = Depends(get_db_session)) -> ProductService:
    """Dependency to provide ProductService (for buisiness logic and data validation) which operates ProductRepository for db session management."""
    return ProductService(ProductRepository(session=session))


def get_category_service(session: AsyncSession = Depends(get_db_session)) -> CategoryService:
    """Dependency to provide CategoryService (for buisiness logic and data validation) which operates CategoryRepository for db session management."""
    return CategoryService(CategoryRepository(session=session))


def get_review_service(session: AsyncSession = Depends(get_db_session)) -> ReviewService:
    """Dependency to provide ReviewService (for buisiness logic and data validation) which operates ReviewRepository for db session management."""
    return ReviewService(ReviewRepository(session=session))
        
    
product_service_dependency = Annotated[ProductService, Depends(get_product_service)]
category_service_dependency = Annotated[CategoryService, Depends(get_category_service)]
review_service_dependency = Annotated[ReviewService, Depends(get_review_service)]
