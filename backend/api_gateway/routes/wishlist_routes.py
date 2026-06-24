from fastapi import APIRouter, Request, Depends

from gateway.apigateway import api_gateway_manager
from dependencies.auth_dependencies import get_current_user
from shared.schemas.user_schemas import CurrentUserInfo
from shared.enums.services_enums import Services
from shared.shared_instances import api_gateway_rate_limit_manager


wishlist_proxy = APIRouter(tags=["Wishlist Service Proxy"])


@wishlist_proxy.get("/wishlists/me", summary="Get current user's wishlist")
@api_gateway_rate_limit_manager.ratelimiter(times=10, seconds=60)
async def get_my_wishlist(request: Request, current_user: CurrentUserInfo = Depends(get_current_user)):
    return await api_gateway_manager.forward_request(
        service_name=Services.WISHLIST_SERVICE,
        request=request
    )


@wishlist_proxy.post("/wishlists/me/items", summary="Add item to wishlist")
@api_gateway_rate_limit_manager.ratelimiter(times=10, seconds=60)
async def add_item_to_wishlist(request: Request, current_user: CurrentUserInfo = Depends(get_current_user)):
    return await api_gateway_manager.forward_request(
        service_name=Services.WISHLIST_SERVICE,
        request=request
    )


@wishlist_proxy.delete("/wishlists/me/items/{item_id}", summary="Remove item from wishlist")
@api_gateway_rate_limit_manager.ratelimiter(times=10, seconds=60)
async def remove_item_from_wishlist(request: Request, item_id: str, current_user: CurrentUserInfo = Depends(get_current_user)):
    return await api_gateway_manager.forward_request(
        service_name=Services.WISHLIST_SERVICE,
        request=request
    )
