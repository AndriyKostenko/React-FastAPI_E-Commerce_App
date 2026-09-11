"""Scheduled retry of CJ orders that are created but not yet paid.

The event consumer tries to pay each CJ order as soon as it is created. This
task picks up what that attempt could not finish: CJ unreachable, the order
not confirmed yet, or a CJ balance that needed topping up.
"""

from datetime import datetime, timezone
from typing import Any

from resources import create_database_manager, logger, settings
from service_layer.cj_api_client import CJDropshippingAPIClient
from service_layer.cj_order_payment_service import CJOrderPaymentService
from tasks.broker import taskiq_broker


@taskiq_broker.task(schedule=[{"cron": "*/5 * * * *"}])
async def pay_unpaid_cj_orders() -> dict[str, Any]:
    """Advance every unpaid CJ order due for another payment attempt."""
    cj_api_client = CJDropshippingAPIClient(settings)
    database = create_database_manager()
    try:
        payment_service = CJOrderPaymentService(
            settings=settings,
            database=database,
            api_client=cj_api_client,
            logger=logger,
        )
        report = await payment_service.advance_due()
        return {
            "run_at": datetime.now(timezone.utc).isoformat(),
            **report.as_dict(),
        }
    finally:
        try:
            await cj_api_client.close()
        finally:
            await database.close()
