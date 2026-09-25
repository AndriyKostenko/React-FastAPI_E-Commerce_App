from uuid import UUID

from fastapi import APIRouter, Request

from dependencies.dependencies import shipment_service_dependency, shipping_method_service_dependency
from schemas.shipping_schemas import (
    CreateShipment,
    CreateShippingMethod,
    ShippingMethodSchema,
    ShippingRateRequest,
    ShipmentSchema,
    UpdateShipment,
    UpdateShippingMethod,
)
from shared.auth.route_guards import AdminDep, CallerDep, ensure_owner_or_admin

shipping_routes = APIRouter(tags=["Shipping"])


@shipping_routes.get("/shipping/methods", response_model=list[ShippingMethodSchema], summary="List active shipping methods")
async def list_active_shipping_methods(
    request: Request,
    shipping_method_service: shipping_method_service_dependency,
):
    return await shipping_method_service.list_active_methods()


@shipping_routes.get("/shipping/methods/all", response_model=list[ShippingMethodSchema], summary="List all shipping methods")
async def list_all_shipping_methods(
    admin: AdminDep,
    request: Request,
    shipping_method_service: shipping_method_service_dependency,
):
    return await shipping_method_service.list_all_methods()


@shipping_routes.get("/shipping/methods/{method_id}", response_model=ShippingMethodSchema, summary="Get a shipping method")
async def get_shipping_method(
    request: Request,
    method_id: UUID,
    shipping_method_service: shipping_method_service_dependency,
):
    return await shipping_method_service.get_method_by_id(method_id)


@shipping_routes.post("/shipping/methods", response_model=ShippingMethodSchema, summary="Create a shipping method")
async def create_shipping_method(
    admin: AdminDep,
    request: Request,
    method_data: CreateShippingMethod,
    shipping_method_service: shipping_method_service_dependency,
):
    return await shipping_method_service.create_method(method_data)


@shipping_routes.patch("/shipping/methods/{method_id}", response_model=ShippingMethodSchema, summary="Update a shipping method")
async def update_shipping_method(
    admin: AdminDep,
    request: Request,
    method_id: UUID,
    method_data: UpdateShippingMethod,
    shipping_method_service: shipping_method_service_dependency,
):
    return await shipping_method_service.update_method(method_id, method_data)


@shipping_routes.delete("/shipping/methods/{method_id}", summary="Delete a shipping method")
async def delete_shipping_method(
    admin: AdminDep,
    request: Request,
    method_id: UUID,
    shipping_method_service: shipping_method_service_dependency,
):
    await shipping_method_service.delete_method(method_id)
    return {"detail": f"Shipping method {method_id} deleted"}


@shipping_routes.post("/shipping/rates", summary="Calculate shipping rates")
async def calculate_shipping_rates(
    request: Request,
    rate_request: ShippingRateRequest,
    shipment_service: shipment_service_dependency,
):
    return await shipment_service.calculate_rate(rate_request)


@shipping_routes.post("/shipments", response_model=ShipmentSchema, summary="Create a shipment")
async def create_shipment(
    admin: AdminDep,
    request: Request,
    shipment_data: CreateShipment,
    shipment_service: shipment_service_dependency,
):
    return await shipment_service.create_shipment(shipment_data)


@shipping_routes.get("/shipments/{shipment_id}", response_model=ShipmentSchema, summary="Get shipment by ID")
async def get_shipment_by_id(
    caller: CallerDep,
    request: Request,
    shipment_id: UUID,
    shipment_service: shipment_service_dependency,
):
    # A shipment carries the buyer's address: owner or admin only (previously
    # any signed-in user could read any shipment).
    shipment = await shipment_service.get_shipment_by_id(shipment_id)
    ensure_owner_or_admin(caller, shipment.user_id)
    return shipment


@shipping_routes.get("/shipments/order/{order_id}", response_model=ShipmentSchema, summary="Get shipment by order ID")
async def get_shipment_by_order_id(
    caller: CallerDep,
    request: Request,
    order_id: UUID,
    shipment_service: shipment_service_dependency,
):
    shipment = await shipment_service.get_shipment_by_order_id(order_id)
    ensure_owner_or_admin(caller, shipment.user_id)
    return shipment


@shipping_routes.patch("/shipments/{shipment_id}", response_model=ShipmentSchema, summary="Update a shipment")
async def update_shipment(
    admin: AdminDep,
    request: Request,
    shipment_id: UUID,
    update_data: UpdateShipment,
    shipment_service: shipment_service_dependency,
):
    return await shipment_service.update_shipment(shipment_id, update_data)
