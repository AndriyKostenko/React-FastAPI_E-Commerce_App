from uuid import UUID

from fastapi import APIRouter, Request, Depends

from gateway.apigateway import api_gateway_manager
from dependencies.auth_dependencies import get_current_user, require_user_or_admin, require_admin
from shared.schemas.user_schemas import CurrentUserInfo
from shared.enums.services_enums import Services
from shared.shared_instances import api_gateway_rate_limit_manager

shipping_proxy = APIRouter(tags=["Shipping Service Proxy"])


@shipping_proxy.get("/shipping/methods", summary="List active shipping methods")
@api_gateway_rate_limit_manager.ratelimiter(times=30, seconds=60)
async def list_active_shipping_methods(request: Request):
    return await api_gateway_manager.forward_request(
        service_name=Services.SHIPPING_SERVICE,
        request=request,
    )


@shipping_proxy.get("/shipping/methods/all", summary="List all shipping methods")
@api_gateway_rate_limit_manager.ratelimiter(times=30, seconds=60)
async def list_all_shipping_methods(
    request: Request,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    require_admin(current_user)
    return await api_gateway_manager.forward_request(
        service_name=Services.SHIPPING_SERVICE,
        request=request,
    )


@shipping_proxy.get("/shipping/methods/{method_id}", summary="Get a shipping method")
@api_gateway_rate_limit_manager.ratelimiter(times=30, seconds=60)
async def get_shipping_method(request: Request, method_id: UUID):
    return await api_gateway_manager.forward_request(
        service_name=Services.SHIPPING_SERVICE,
        request=request,
    )


@shipping_proxy.post("/shipping/methods", summary="Create a shipping method")
@api_gateway_rate_limit_manager.ratelimiter(times=10, seconds=60)
async def create_shipping_method(
    request: Request,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    require_admin(current_user)
    return await api_gateway_manager.forward_request(
        service_name=Services.SHIPPING_SERVICE,
        request=request,
    )


@shipping_proxy.patch("/shipping/methods/{method_id}", summary="Update a shipping method")
@api_gateway_rate_limit_manager.ratelimiter(times=10, seconds=60)
async def update_shipping_method(
    request: Request,
    method_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    require_admin(current_user)
    return await api_gateway_manager.forward_request(
        service_name=Services.SHIPPING_SERVICE,
        request=request,
    )


@shipping_proxy.delete("/shipping/methods/{method_id}", summary="Delete a shipping method")
@api_gateway_rate_limit_manager.ratelimiter(times=10, seconds=60)
async def delete_shipping_method(
    request: Request,
    method_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    require_admin(current_user)
    return await api_gateway_manager.forward_request(
        service_name=Services.SHIPPING_SERVICE,
        request=request,
    )


@shipping_proxy.post("/shipping/rates", summary="Calculate shipping rates")
@api_gateway_rate_limit_manager.ratelimiter(times=20, seconds=60)
async def calculate_shipping_rates(request: Request):
    return await api_gateway_manager.forward_request(
        service_name=Services.SHIPPING_SERVICE,
        request=request,
    )


@shipping_proxy.post("/shipments", summary="Create a shipment")
@api_gateway_rate_limit_manager.ratelimiter(times=10, seconds=60)
async def create_shipment(
    request: Request,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    require_admin(current_user)
    return await api_gateway_manager.forward_request(
        service_name=Services.SHIPPING_SERVICE,
        request=request,
    )


@shipping_proxy.get("/shipments/{shipment_id}", summary="Get shipment by ID")
@api_gateway_rate_limit_manager.ratelimiter(times=20, seconds=60)
async def get_shipment_by_id(
    request: Request,
    shipment_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    return await api_gateway_manager.forward_request(
        service_name=Services.SHIPPING_SERVICE,
        request=request,
    )


@shipping_proxy.get("/shipments/order/{order_id}", summary="Get shipment by order ID")
@api_gateway_rate_limit_manager.ratelimiter(times=20, seconds=60)
async def get_shipment_by_order_id(
    request: Request,
    order_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    return await api_gateway_manager.forward_request(
        service_name=Services.SHIPPING_SERVICE,
        request=request,
    )


@shipping_proxy.patch("/shipments/{shipment_id}", summary="Update a shipment")
@api_gateway_rate_limit_manager.ratelimiter(times=10, seconds=60)
async def update_shipment(
    request: Request,
    shipment_id: UUID,
    current_user: CurrentUserInfo = Depends(get_current_user),
):
    require_admin(current_user)
    return await api_gateway_manager.forward_request(
        service_name=Services.SHIPPING_SERVICE,
        request=request,
    )
