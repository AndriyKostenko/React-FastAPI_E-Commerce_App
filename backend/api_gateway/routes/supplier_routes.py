from fastapi import APIRouter, Request, Depends

from gateway.apigateway import api_gateway_manager
from dependencies.auth_dependencies import require_admin


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
