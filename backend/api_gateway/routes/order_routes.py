from uuid import UUID

from fastapi import APIRouter, Request, Depends

from resources import api_gateway_manager, rate_limited
from dependencies.auth_dependencies import (get_current_user,
                                            require_admin,
                                            require_user_or_admin)
from shared.utils.customized_json_response import JSONResponse
from shared.contracts.auth import TokenClaims as CurrentUserInfo


order_proxy = APIRouter(tags=["Order Service Proxy"])


@order_proxy.post("/orders/quote", summary="Build a canonical order quote")
@rate_limited(times=30, seconds=60)
async def quote_order(
    request: Request,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


# ==================== PUBLIC ENDPOINTS ====================

@order_proxy.post("/orders", summary="Create a new order")
@rate_limited(times=10, seconds=60)
async def create_order(
    request: Request,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    payload = await request.json()
    override_body = {
        **payload,
        "user_id": str(current_user.id),
        "user_email": current_user.email,
    }
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
        override_body=override_body,
    )


@order_proxy.get("/orders", summary="Get all orders")
async def get_all_orders(
    request: Request,
    current_user: CurrentUserInfo = Depends(require_admin),
):
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


@order_proxy.get("/orders/user/{user_id}", summary="Get orders by user ID")
async def get_orders_by_user_id(request: Request,
                                user_id: UUID,
                                current_user: CurrentUserInfo = Depends(get_current_user)):
    require_user_or_admin(current_user, target_user_id=user_id)
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


@order_proxy.get("/orders/{order_id}", summary="Get order by ID")
async def get_order_by_id(
    request: Request,
    order_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    upstream = await api_gateway_manager.request_service(
        request, "order-service", f"/orders/{order_id}"
    )
    content = upstream.json()
    if upstream.is_success:
        require_user_or_admin(current_user, target_user_id=UUID(content["user_id"]))
    return JSONResponse(content=content, status_code=upstream.status_code)


# ==================== AUTHENTICATED ENDPOINTS ====================

@order_proxy.patch("/orders/{order_id}/cancel", summary="Cancel an order")
async def cancel_order(
    request: Request,
    order_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    upstream = await api_gateway_manager.request_service(
        request, "order-service", f"/orders/{order_id}"
    )
    if upstream.is_success:
        require_user_or_admin(
            current_user, target_user_id=UUID(upstream.json()["user_id"])
        )
    else:
        return JSONResponse(content=upstream.json(), status_code=upstream.status_code)
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


@order_proxy.patch("/orders/{order_id}", summary="Update an order")
async def update_order(
    request: Request,
    order_id: UUID,
    current_user: CurrentUserInfo = Depends(require_admin),
):
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


# ==================== ADMIN ENDPOINTS ====================

@order_proxy.delete("/orders/{order_id}", summary="Delete an order (admin only)")
async def delete_order(
    request: Request,
    order_id: UUID,
    current_user: CurrentUserInfo = Depends(require_admin),
):
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


@order_proxy.get("/admin/schema/orders")
async def get_order_schema_for_admin_js(request: Request):
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request
    )
