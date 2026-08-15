from fastapi import APIRouter, Request, Depends

from resources import api_gateway_manager, rate_limited
from dependencies.auth_dependencies import get_current_user
from shared.contracts.auth import TokenClaims as CurrentUserInfo
from shared.enums.services_enums import Services


wishlist_proxy = APIRouter(tags=["Wishlist Service Proxy"])


@wishlist_proxy.get("/wishlists/me", summary="Get current user's wishlist")
@rate_limited(times=10, seconds=60)
async def get_my_wishlist(request: Request, current_user: CurrentUserInfo = Depends(get_current_user)):
    return await api_gateway_manager.forward_request(
        service_name=Services.WISHLIST_SERVICE,
        request=request
    )


@wishlist_proxy.post("/wishlists/me/items", summary="Add item to wishlist")
@rate_limited(times=10, seconds=60)
async def add_item_to_wishlist(request: Request, current_user: CurrentUserInfo = Depends(get_current_user)):
    return await api_gateway_manager.forward_request(
        service_name=Services.WISHLIST_SERVICE,
        request=request
    )


@wishlist_proxy.delete("/wishlists/me/items/{item_id}", summary="Remove item from wishlist")
@rate_limited(times=10, seconds=60)
async def remove_item_from_wishlist(request: Request, item_id: str, current_user: CurrentUserInfo = Depends(get_current_user)):
    return await api_gateway_manager.forward_request(
        service_name=Services.WISHLIST_SERVICE,
        request=request
    )
