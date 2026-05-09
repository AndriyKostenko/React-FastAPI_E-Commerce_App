from uuid import UUID

from fastapi import APIRouter, Request, Depends

from gateway.apigateway import api_gateway_manager
from dependencies.auth_dependencies import (get_current_user,
                                            require_admin,
                                            require_user_or_admin)
from shared.utils.customized_json_response import JSONResponse
from shared.schemas.user_schemas import CurrentUserInfo


order_proxy = APIRouter(tags=["Order Service Proxy"])


# ==================== PUBLIC ENDPOINTS ====================

@order_proxy.post("/orders", summary="Create a new order")
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
async def get_all_orders(request: Request):
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


@order_proxy.get("/orders/user/{user_id}", summary="Get orders by user ID")
async def get_orders_by_user_id(
    request: Request,
    user_id: UUID,
    current_user: CurrentUserInfo = Depends(require_user_or_admin),
):
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
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


# ==================== AUTHENTICATED ENDPOINTS ====================

@order_proxy.patch("/orders/{order_id}/cancel", summary="Cancel an order")
async def cancel_order(
    request: Request,
    order_id: UUID,
    current_user: CurrentUserInfo = Depends(require_user_or_admin),
):
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


@order_proxy.patch("/orders/{order_id}", summary="Update an order")
async def update_order(
    request: Request,
    order_id: UUID,
    current_user: CurrentUserInfo = Depends(require_user_or_admin),
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
