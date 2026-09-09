from fastapi import APIRouter, Request, Depends

from resources import api_gateway_manager
from dependencies.auth_dependencies import get_current_user, require_admin


supplier_proxy = APIRouter(tags=["Supplier Service Proxy"])


@supplier_proxy.get("/cjdropshipping/products", summary="Search CJDropshipping products")
async def get_products_from_cjdropshipping(request: Request):
    """PUBLIC - Search products directly from CJDropshipping."""
    return await api_gateway_manager.forward_request(
        service_name="supplier-service",
        request=request,
    )


@supplier_proxy.get("/cjdropshipping/products/{pid}", summary="Get CJDropshipping product details")
async def get_cjdropshipping_product_details(request: Request, pid: str):
    """PUBLIC - Fetch raw CJDropshipping product details by pid."""
    return await api_gateway_manager.forward_request(
        service_name="supplier-service",
        request=request,
    )


@supplier_proxy.post("/cjdropshipping/freight/quote", summary="Quote CJ shipping for a cart")
async def quote_cjdropshipping_freight(request: Request, current_user: dict = Depends(get_current_user)):
    """AUTHENTICATED - Price CJ shipping for a cart at checkout.

    Authentication is required because every call costs one live CJ API request.
    """
    return await api_gateway_manager.forward_request(
        service_name="supplier-service",
        request=request,
    )


@supplier_proxy.post("/cjdropshipping/sync", summary="Synchronize CJ Dropshipping products")
async def sync_cjdropshipping_products(request: Request, current_user: dict = Depends(require_admin)):
    """ADMIN ONLY - Trigger CJ Dropshipping sync."""
    return await api_gateway_manager.forward_request(
        service_name="supplier-service",
        request=request,
    )


@supplier_proxy.post("/suppliers/{supplier_id}/sync", summary="Trigger a supplier sync")
async def sync_supplier_products(request: Request,supplier_id: str,current_user: dict = Depends(require_admin)):
    """ADMIN ONLY - Trigger a manual supplier sync."""
    return await api_gateway_manager.forward_request(
        service_name="supplier-service",
        request=request,
    )
