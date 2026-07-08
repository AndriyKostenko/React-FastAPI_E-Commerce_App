from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from dependencies.dependencies import sync_orchestrator_dependency
from service_layer.cj_product_provider import CJDropshippingProductProvider
from service_layer.sync_orchestrator_service import SupplierSyncOrchestrator
from shared.schemas.dropshipping_schemas import CJProductsFilterParams
from shared.schemas.product_schemas import CJProductPreview
from shared.schemas.supplier_schemas import SupplierSyncRunSummary
from shared.settings import Settings
from shared.shared_instances import settings


supplier_routes = APIRouter(tags=["suppliers"])


def get_cj_provider(settings_instance: Settings = settings) -> CJDropshippingProductProvider:
    """Dependency to get the CJDropshipping product provider."""
    return CJDropshippingProductProvider(settings_instance)


@supplier_routes.get(
    "/cjdropshipping/products",
    response_model=list[CJProductPreview],
    response_description="Products from CJDropshipping",
    status_code=status.HTTP_200_OK,
)
async def get_products_from_cjdropshipping(
    cj_provider: Annotated[CJDropshippingProductProvider, Depends(get_cj_provider)],
    filters_query: Annotated[CJProductsFilterParams, Query()],
) -> list[CJProductPreview]:
    """Search products directly from CJDropshipping."""
    page = await cj_provider.search_products(filters_query=filters_query)
    return [
        CJProductPreview(
            pid=product.supplier_pid or "",
            name=product.name,
            sku=product.sku,
            image_url=product.image_url,
            price=product.price,
            quantity=product.quantity,
            in_stock=product.in_stock,
            category_id=str(product.category_id) if product.category_id else None,
        )
        for product in page.products
    ]


@supplier_routes.get(
    "/cjdropshipping/products/{pid}",
    response_model=dict[str, Any],
    response_description="Raw CJDropshipping product details by pid",
    status_code=status.HTTP_200_OK,
)
async def get_cjdropshipping_product_details(
    pid: str,
    cj_provider: Annotated[CJDropshippingProductProvider, Depends(get_cj_provider)],
) -> dict[str, Any]:
    """Fetch raw product details from CJDropshipping by pid."""
    return await cj_provider.get_product_details(supplier_pid=pid)


@supplier_routes.post(
    "/cjdropshipping/sync",
    response_model=SupplierSyncRunSummary,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Synchronize CJ Dropshipping products",
)
async def sync_cjdropshipping_products(
    sync_orchestrator: sync_orchestrator_dependency,
    filters_query: Annotated[CJProductsFilterParams, Query()],
    fetch_details: bool = Query(default=True, description="Fetch full details/variants for each product"),
) -> SupplierSyncRunSummary:
    """Pull products from CJDropshipping and emit import events to product_service."""
    sync_state = await sync_orchestrator.run_sync(
        supplier_id="cjdropshipping",
        filters=filters_query,
        fetch_details=fetch_details,
    )
    return SupplierSyncRunSummary(
        supplier_id=sync_state.supplier_id,
        fetch_id=sync_state.fetch_id,
        started_at=sync_state.started_at,
        finished_at=sync_state.finished_at,
        products_fetched=sync_state.products_fetched,
        products_emitted=sync_state.products_emitted,
        status=sync_state.status,
        errors=[sync_state.error_message] if sync_state.error_message else [],
    )


@supplier_routes.post(
    "/suppliers/{supplier_id}/sync",
    response_model=SupplierSyncRunSummary,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a manual supplier sync",
)
async def sync_supplier_products(
    supplier_id: str,
    sync_orchestrator: sync_orchestrator_dependency,
    filters_query: Annotated[CJProductsFilterParams, Query()],
    fetch_details: bool = Query(default=True, description="Fetch full details/variants for each product"),
) -> SupplierSyncRunSummary:
    """Manually trigger a supplier sync and emit product import events."""
    sync_state = await sync_orchestrator.run_sync(
        supplier_id=supplier_id,
        filters=filters_query,
        fetch_details=fetch_details,
    )
    return SupplierSyncRunSummary(
        supplier_id=sync_state.supplier_id,
        fetch_id=sync_state.fetch_id,
        started_at=sync_state.started_at,
        finished_at=sync_state.finished_at,
        products_fetched=sync_state.products_fetched,
        products_emitted=sync_state.products_emitted,
        status=sync_state.status,
        errors=[sync_state.error_message] if sync_state.error_message else [],
    )
