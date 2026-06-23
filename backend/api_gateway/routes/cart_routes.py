from uuid import UUID

from fastapi import APIRouter, Request, Depends

from gateway.apigateway import api_gateway_manager
from dependencies.auth_dependencies import get_current_user, require_user_or_admin
from shared.schemas.user_schemas import CurrentUserInfo
from shared.enums.services_enums import Services
from shared.shared_instances import api_gateway_rate_limit_manager

cart_proxy = APIRouter(tags=["Cart Service Proxy"])

@cart_proxy.get("/users/{user_id}/cart", summary="Get or create user cart")
@api_gateway_rate_limit_manager.ratelimiter(times=10, seconds=60)
async def get_cart(request: Request, user_id: UUID, current_user: CurrentUserInfo = Depends(get_current_user)):
    require_user_or_admin(current_user, target_user_id=user_id)
    return await api_gateway_manager.forward_request(
        service_name=Services.CART_SERVICE,
        request=request
    )

@cart_proxy.get("/users/{user_id}/cart/summary", summary="Get cart summary")
@api_gateway_rate_limit_manager.ratelimiter(times=10, seconds=60)
async def get_cart_summary(request: Request, user_id: UUID, current_user: CurrentUserInfo = Depends(get_current_user)):
    require_user_or_admin(current_user, target_user_id=user_id)
    return await api_gateway_manager.forward_request(
        service_name=Services.CART_SERVICE,
        request=request
    )

@cart_proxy.post("/users/{user_id}/cart/items", summary="Add item to cart")
@api_gateway_rate_limit_manager.ratelimiter(times=10, seconds=60)
async def add_item_to_cart(request: Request, user_id: UUID, current_user: CurrentUserInfo = Depends(get_current_user)):
    require_user_or_admin(current_user, target_user_id=user_id)
    return await api_gateway_manager.forward_request(
        service_name=Services.CART_SERVICE,
        request=request
    )

@cart_proxy.put("/users/{user_id}/cart/items/{item_id}", summary="Update cart item quantity")
@api_gateway_rate_limit_manager.ratelimiter(times=10, seconds=60)
async def update_cart_item(request: Request, user_id: UUID, item_id: UUID, current_user: CurrentUserInfo = Depends(get_current_user)):
    require_user_or_admin(current_user, target_user_id=user_id)
    return await api_gateway_manager.forward_request(
        service_name=Services.CART_SERVICE,
        request=request
    )

@cart_proxy.delete("/users/{user_id}/cart/items/{item_id}", summary="Remove item from cart")
@api_gateway_rate_limit_manager.ratelimiter(times=10, seconds=60)
async def remove_cart_item(request: Request, user_id: UUID, item_id: UUID, current_user: CurrentUserInfo = Depends(get_current_user)):
    require_user_or_admin(current_user, target_user_id=user_id)
    return await api_gateway_manager.forward_request(
        service_name=Services.CART_SERVICE,
        request=request
    )

@cart_proxy.delete("/users/{user_id}/cart", summary="Clear cart")
@api_gateway_rate_limit_manager.ratelimiter(times=10, seconds=60)
async def clear_cart(request: Request, user_id: UUID, current_user: CurrentUserInfo = Depends(get_current_user)):
    require_user_or_admin(current_user, target_user_id=user_id)
    return await api_gateway_manager.forward_request(
        service_name=Services.CART_SERVICE,
        request=request
    )
