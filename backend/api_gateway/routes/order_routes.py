from fastapi import APIRouter, Request

from apigateway import api_gateway_manager
from dependencies.auth_dependencies import (get_current_user,
                                            require_admin,
                                            require_user_or_admin)


order_proxy = APIRouter(tags=["Order Service Proxy"])


# ==================== PUBLIC ENDPOINTS ====================

@order_proxy.post("/orders", summary="Create a new order")
async def create_order(request: Request):
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )


@order_proxy.get("/orders", summary="Get all orders")
async def get_all_products(request: Request):
    """PUBLIC - Anyone can browse products"""
    return await api_gateway_manager.forward_request(
        service_name="order-service",
        request=request,
    )
    
