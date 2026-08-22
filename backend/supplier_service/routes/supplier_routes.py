from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from dependencies.dependencies import cj_provider_dependency, sync_orchestrator_dependency
from schemas.dropshipping_schemas import CJProductsFilterParams
from schemas.supplier_schemas import CJProductPreview, SupplierSyncRunSummary


supplier_routes = APIRouter(tags=["suppliers"])


def _to_sync_summary(sync_state) -> SupplierSyncRunSummary:
    return SupplierSyncRunSummary(
        supplier_id=sync_state.supplier_id,
        fetch_id=sync_state.fetch_id,
        started_at=sync_state.started_at,
        finished_at=sync_state.finished_at,
        products_fetched=sync_state.products_fetched,
        products_emitted=sync_state.products_emitted,
        total_batches=sync_state.total_batches,
        processed_batches=sync_state.processed_batches,
        products_imported=sync_state.products_imported,
        products_updated=sync_state.products_updated,
        products_failed=sync_state.products_failed,
        status=sync_state.status,
        errors=[sync_state.error_message] if sync_state.error_message else [],
    )


@supplier_routes.get(
    "/cjdropshipping/products",
    response_model=list[CJProductPreview],
    response_description="Products from CJDropshipping",
    status_code=status.HTTP_200_OK,
)
async def get_products_from_cjdropshipping(
    cj_provider: cj_provider_dependency,
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
            supplier_category_id=product.supplier_category_id,
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
    cj_provider: cj_provider_dependency,
) -> dict[str, Any]:
    """Fetch raw product details from CJDropshipping by pid."""
    return await cj_provider.get_product_details(supplier_pid=pid)


@supplier_routes.post(
    "/cjdropshipping/products/{pid}/sync",
    response_model=SupplierSyncRunSummary,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Synchronize one CJ Dropshipping product",
)
async def sync_cjdropshipping_product(
    pid: str,
    sync_orchestrator: sync_orchestrator_dependency,
) -> SupplierSyncRunSummary:
    """Fetch one CJ product by pid and emit a single import event."""
    sync_state = await sync_orchestrator.run_product_sync(
        supplier_id="cjdropshipping",
        supplier_pid=pid,
    )
    return _to_sync_summary(sync_state)


@supplier_routes.post(
    "/cjdropshipping/sync",
    response_model=SupplierSyncRunSummary,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Synchronize CJ Dropshipping products",
)
async def sync_cjdropshipping_products(
    sync_orchestrator: sync_orchestrator_dependency,
    filters_query: Annotated[CJProductsFilterParams, Query()],
) -> SupplierSyncRunSummary:
    """Pull products from CJDropshipping and emit import events to product_service."""
    sync_state = await sync_orchestrator.run_sync(
        supplier_id="cjdropshipping",
        filters=filters_query,
        fetch_details=True,
    )
    return _to_sync_summary(sync_state)


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
) -> SupplierSyncRunSummary:
    """Manually trigger a supplier sync and emit product import events."""
    sync_state = await sync_orchestrator.run_sync(
        supplier_id=supplier_id,
        filters=filters_query,
        fetch_details=True,
    )
    return _to_sync_summary(sync_state)
