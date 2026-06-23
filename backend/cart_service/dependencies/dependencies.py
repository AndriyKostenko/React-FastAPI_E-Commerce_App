from typing import Annotated
from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.shared_instances import cart_service_database_session_manager
from service_layer.cart_services import CartService
from database_layer.cart_repository import CartRepository

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Providing a transactional scope around for each series (request) of operations with database.
    """
    async with cart_service_database_session_manager.transaction() as session:
        yield session

def get_cart_service(session: AsyncSession = Depends(get_db_session)) -> CartService:
    """Dependency to provide CartService which operates CartRepository."""
    return CartService(CartRepository(session=session))

cart_service_dependency = Annotated[CartService, Depends(get_cart_service)]
