from typing import Annotated
from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from shared.shared_instances import wishlist_service_database_session_manager
from service_layer.wishlist_service import WishlistService
from database_layer.wishlist_repository import WishlistRepository


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Providing a transactional scope around for each series (request) of operations with database.
    """
    async with wishlist_service_database_session_manager.transaction() as session:
        yield session


def get_wishlist_service(session: AsyncSession = Depends(get_db_session)) -> WishlistService:
    """Dependency to provide WishlistService which operates WishlistRepository."""
    return WishlistService(WishlistRepository(session=session))


def get_current_user(request: Request) -> dict:
    """Extract the current authenticated user from request state (set by API Gateway)."""
    return request.state.current_user


wishlist_service_dependency = Annotated[WishlistService, Depends(get_wishlist_service)]
current_user_dependency = Annotated[dict, Depends(get_current_user)]
