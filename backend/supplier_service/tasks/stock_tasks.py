"""Hourly refresh of the catalogue's CJ stock from CJ's US warehouses.

The catalogue sync only ever sees products CJ still lists as stocked in the
US, so a product that sells out there would keep its old stock forever. This
task asks CJ about every CJ product we sell. See CJStockRefreshService.
"""

from datetime import datetime, timezone
from typing import Any

from resources import create_database_manager, logger, settings
from service_layer.cj_api_client import CJDropshippingAPIClient
from service_layer.cj_product_provider import CJDropshippingProductProvider
from service_layer.cj_stock_refresh_service import CJStockRefreshService
from service_layer.product_service_client import ProductServiceClient
from tasks.broker import taskiq_broker


@taskiq_broker.task(schedule=[{"cron": "0 * * * *"}])
async def refresh_cj_stock() -> dict[str, Any]:
    """Send product-service the current sellable US stock of every CJ product we sell.

    A run that is still going when the next hour starts is not doubled: the
    refresh holds a database lock, and a second run returns at once.
    """
    cj_api_client = CJDropshippingAPIClient(settings)
    product_client = ProductServiceClient(settings)
    database = create_database_manager()
    try:
        report = await CJStockRefreshService(
            settings=settings,
            database=database,
            provider=CJDropshippingProductProvider(settings, api_client=cj_api_client, logger=logger),
            product_client=product_client,
            logger=logger,
        ).refresh()
        return {"run_at": datetime.now(timezone.utc).isoformat(), **report.as_dict()}
    finally:
        try:
            await product_client.close()
            await cj_api_client.close()
        finally:
            await database.close()
