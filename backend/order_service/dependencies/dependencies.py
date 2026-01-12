from typing import AsyncGenerator, Annotated

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from service_layer.order_service import OrderService
from shared.shared_instances import order_service_database_session_manager # type: ignore
from database_layer.order_repository import OrderRepository
from product_service.database_layer.product_repository import ProductRepository


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Providing a transactional scope around for each series (request) of operations with database.
    FastAPI
     └─ get_db_session()
         └─ async with DatabaseSessionManager.transaction()
             └─ async with AsyncSession()
    """
    async with order_service_database_session_manager.transaction() as session:
        yield session


def get_order_service(session: AsyncSession = Depends(get_db_session)) -> OrderService:
    """Dependency to provide OrderService (for buisiness logic and data validation) which operates OrderRepository(inherits BaseRepository) for db session management."""
    return OrderService(
        order_repository=OrderRepository(session=session),
        product_repository=ProductRepository(session=session)
    )


order_service_dependency = Annotated[OrderService, Depends(get_order_service)]
