"""Scheduled polling of CJ Dropshipping order tracking state.

CJ offers no webhook, so a periodic task is the only way an accepted order ever
progresses to shipped/delivered — or is discovered to have been cancelled on
CJ's side, which the order saga needs in order to refund the customer.
"""

from datetime import datetime, timezone
from typing import Any

from resources import create_database_manager, logger, settings
from service_layer.cj_api_client import CJDropshippingAPIClient
from service_layer.cj_order_tracking_service import CJOrderTrackingService
from tasks.broker import taskiq_broker


@taskiq_broker.task(schedule=[{"cron": "*/5 * * * *"}])
async def poll_cj_order_tracking() -> dict[str, Any]:
    """Refresh every open CJ order that is due for a tracking check.

    The task runs every 5 minutes but each order is only re-queried after
    ``CJ_DROPSHIPPING_TRACKING_POLL_INTERVAL_MINUTES``, so the schedule can be
    tightened without multiplying CJ API calls.
    """
    cj_api_client = CJDropshippingAPIClient(settings)
    database = create_database_manager()
    try:
        tracking_service = CJOrderTrackingService(
            settings=settings,
            database=database,
            api_client=cj_api_client,
            logger=logger,
        )
        report = await tracking_service.poll_open_orders()
        return {
            "polled_at": datetime.now(timezone.utc).isoformat(),
            **report.as_dict(),
        }
    finally:
        try:
            await cj_api_client.close()
        finally:
            await database.close()
