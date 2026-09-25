from typing import Annotated
from collections.abc import AsyncGenerator

from aiohttp import ClientSession
from fastapi import Depends, Request
from starlette.requests import HTTPConnection
from sqlalchemy.ext.asyncio import AsyncSession

from shared.utils.authenticated_caller import AuthenticatedCaller

from resources import WishlistApiResources, get_wishlist_api_resources
from service_layer.wishlist_service import WishlistService
from database_layer.wishlist_repository import WishlistRepository



def get_resources(connection: HTTPConnection) -> WishlistApiResources:
    """Return resources owned by the current FastAPI lifespan."""
    return get_wishlist_api_resources(connection)


resources_dependency = Annotated[WishlistApiResources, Depends(get_resources)]


# Always depended on with scope="function": FastAPI's default runs a yield
# dependency's exit code after the response is sent, so the commit below ran
# after the client had been told "created" — a commit that then failed lost the
# write silently. Function scope commits before the response goes out.
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
    session: AsyncSession = Depends(get_db_session, scope="function"),
) -> WishlistService:
    """Dependency to provide WishlistService which operates WishlistRepository."""
    return WishlistService(
        WishlistRepository(session=session),
        settings=resources.settings,
        logger=resources.logger,
    )


def get_http_client(resources: resources_dependency) -> ClientSession:
    return resources.http_client


def get_current_user(request: Request) -> AuthenticatedCaller:
    """
    Resolve the caller from the identity headers the API gateway asserts.

    ``request.state`` belongs to this process, so the gateway's own
    ``state.current_user`` never reaches it; the headers are the only channel.
    """
    return AuthenticatedCaller.require(request)


wishlist_service_dependency = Annotated[WishlistService, Depends(get_wishlist_service)]
current_user_dependency = Annotated[AuthenticatedCaller, Depends(get_current_user)]
http_client_dependency = Annotated[ClientSession, Depends(get_http_client)]
