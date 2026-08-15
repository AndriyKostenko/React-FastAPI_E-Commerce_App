from typing import Annotated
from collections.abc import AsyncGenerator

from aiohttp import ClientSession
from fastapi import Depends, Request
from starlette.requests import HTTPConnection
from sqlalchemy.ext.asyncio import AsyncSession

from resources import WishlistApiResources
from service_layer.wishlist_service import WishlistService
from database_layer.wishlist_repository import WishlistRepository



def get_resources(connection: HTTPConnection) -> WishlistApiResources:
    """Return resources owned by the current FastAPI lifespan."""
    return connection.app.state.resources


resources_dependency = Annotated[WishlistApiResources, Depends(get_resources)]


async def get_db_session(
    resources: resources_dependency,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Providing a transactional scope around for each series (request) of operations with database.
    """
    async with resources.database.transaction() as session:
        yield session


def get_wishlist_service(
    resources: resources_dependency,
    session: AsyncSession = Depends(get_db_session),
) -> WishlistService:
    """Dependency to provide WishlistService which operates WishlistRepository."""
    return WishlistService(
        WishlistRepository(session=session),
        settings=resources.settings,
        logger=resources.logger,
    )


def get_http_client(resources: resources_dependency) -> ClientSession:
    return resources.http_client


def get_current_user(request: Request) -> dict:
    """Extract the current authenticated user from request state (set by API Gateway)."""
    return request.state.current_user


wishlist_service_dependency = Annotated[WishlistService, Depends(get_wishlist_service)]
current_user_dependency = Annotated[dict, Depends(get_current_user)]
http_client_dependency = Annotated[ClientSession, Depends(get_http_client)]
