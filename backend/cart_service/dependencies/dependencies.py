from typing import Annotated
from collections.abc import AsyncGenerator

from fastapi import Depends
from starlette.requests import HTTPConnection
from sqlalchemy.ext.asyncio import AsyncSession

from resources import CartApiResources
from service_layer.cart_services import CartService
from database_layer.cart_repository import CartRepository


def get_resources(connection: HTTPConnection) -> CartApiResources:
    """Return resources owned by the current FastAPI lifespan."""
    return connection.app.state.resources


resources_dependency = Annotated[CartApiResources, Depends(get_resources)]


async def get_db_session(
    resources: resources_dependency,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Providing a transactional scope around for each series (request) of operations with database.
    """
    async with resources.database.transaction() as session:
        yield session

def get_cart_service(session: AsyncSession = Depends(get_db_session)) -> CartService:
    """Dependency to provide CartService which operates CartRepository."""
    return CartService(CartRepository(session=session))

cart_service_dependency = Annotated[CartService, Depends(get_cart_service)]
