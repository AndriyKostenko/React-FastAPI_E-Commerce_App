from uuid import UUID

from fastapi import APIRouter, status

from schemas.wishlist_schemas import WishlistSchema, AddWishlistItem
from dependencies.dependencies import (
    current_user_dependency,
    http_client_dependency,
    wishlist_service_dependency,
)


wishlist_routes = APIRouter(
    tags=["wishlist"]
)


@wishlist_routes.get("/wishlists/me",
                     response_model=WishlistSchema,
                     status_code=status.HTTP_200_OK)
async def get_my_wishlist(
    current_user: current_user_dependency,
    wishlist_service: wishlist_service_dependency,
) -> WishlistSchema:
    """Get the wishlist for the authenticated user. Creates one if it doesn't exist."""
    user_id = UUID(current_user["id"])
    return await wishlist_service.get_or_create_wishlist(user_id=user_id)


@wishlist_routes.post("/wishlists/me/items",
                      response_model=WishlistSchema,
                      status_code=status.HTTP_200_OK)
async def add_item_to_wishlist(
    item_data: AddWishlistItem,
    current_user: current_user_dependency,
    wishlist_service: wishlist_service_dependency,
    http_client: http_client_dependency,
) -> WishlistSchema:
    """Add a product to the authenticated user's wishlist."""
    user_id = UUID(current_user["id"])
    return await wishlist_service.add_item_to_wishlist(
        user_id=user_id,
        item_data=item_data,
        http_session=http_client,
    )


@wishlist_routes.delete("/wishlists/me/items/{item_id}",
                        response_model=WishlistSchema,
                        status_code=status.HTTP_200_OK)
async def remove_item_from_wishlist(
    item_id: UUID,
    current_user: current_user_dependency,
    wishlist_service: wishlist_service_dependency,
) -> WishlistSchema:
    """Remove an item from the authenticated user's wishlist."""
    user_id = UUID(current_user["id"])
    return await wishlist_service.remove_item_from_wishlist(
        user_id=user_id,
        item_id=item_id,
    )
