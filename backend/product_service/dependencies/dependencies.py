from typing import Annotated, AsyncGenerator

from fastapi import Depends
from shared.shared_instances import product_service_database_session_manager # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession

from database_layer.category_repository import CategoryRepository
from database_layer.product_image_repository import ProductImageRepository
from database_layer.product_repository import ProductRepository
from database_layer.review_repository import ReviewRepository
from service_layer.category_service import CategoryService
from service_layer.product_image_service import ProductImageService
from service_layer.product_service import ProductService
from service_layer.review_service import ReviewService

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
    """
    Providing a transactional scope around for each series (request) of operations with database.
    FastAPI
     └─ get_db_session()
         └─ async with DatabaseSessionManager.transaction()
             └─ async with AsyncSession()

    """
    async with product_service_database_session_manager.transaction() as session:
        yield session


def get_category_service(
    session: AsyncSession = Depends(get_db_session),
) -> CategoryService:
    """Dependency to provide CategoryService (for buisiness logic and data validation) which operates CategoryRepository(inherits BaseRepository) for db session management."""
    return CategoryService(CategoryRepository(session=session))


def get_review_service(
    session: AsyncSession = Depends(get_db_session),
) -> ReviewService:
    """Dependency to provide ReviewService (for buisiness logic and data validation) which operates ReviewRepository(inherits BaseRepository) for db session management."""
    return ReviewService(ReviewRepository(session=session))


def get_product_image_service(
    session: AsyncSession = Depends(get_db_session),
) -> ProductImageService:
    """Dependency to provide ProductImageService (for image management) which operates ProductImageRepository(inherits BaseRepository) for db session management."""
    return ProductImageService(ProductImageRepository(session=session))


def get_product_service(
    session: AsyncSession = Depends(get_db_session),
    product_image_service: ProductImageService = Depends(get_product_image_service),
) -> ProductService:
    """Dependency to provide ProductService with ProductImageService(for imge handling) (for buisiness logic and data validation) which operates ProductRepository(inherits BaseRepository) for db session management."""
    product_repository = ProductRepository(session=session)
    return ProductService(product_repository, product_image_service)


product_service_dependency = Annotated[ProductService, Depends(get_product_service)]
category_service_dependency = Annotated[CategoryService, Depends(get_category_service)]
review_service_dependency = Annotated[ReviewService, Depends(get_review_service)]
product_image_service_dependency = Annotated[
    ProductImageService, Depends(get_product_image_service)
]
