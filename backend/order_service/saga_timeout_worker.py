"""Cancels abandoned pending Sagas and relies on the order outbox for compensation."""

import asyncio
import signal
from datetime import datetime, timedelta, timezone

from database_layer.order_address_repository import OrderAddressRepository
from database_layer.order_fulfillment_repository import CustomProductionJobRepository
from database_layer.order_item_repository import OrderItemRepository
from database_layer.order_repository import OrderRepository
from database_layer.order_saga_repository import OrderSagaRepository
from models.outbox_models import OutboxEvent
from resources import order_outbox_resources
from service_layer.order_address_service import OrderAddressService
from service_layer.order_item_service import OrderItemService
from service_layer.order_service import OrderService
from service_layer.outbox_event_service import OutboxEventService
from shared.database_layer.outbox_repository import OutboxRepository


async def expire_once(resources) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=resources.settings.ORDER_SAGA_TIMEOUT_SECONDS
    )
    async with resources.database.transaction() as session:
        saga_repository = OrderSagaRepository(session)
        expired = await saga_repository.get_expired_pending_for_update(cutoff)
        if not expired:
            return 0
        service = _order_service(session, saga_repository)
        for saga, order in expired:
            await service._cancel_locked(
                order,
                saga,
                "Order Saga timed out before payment and inventory completed",
            )
        return len(expired)


async def cancel_stalled_supplier_orders(resources) -> int:
    """
    Cancel confirmed orders whose CJ part never got going.

    When CJ cannot take an order (an outage outlasting the event's retries, a
    wallet left unfunded), the order used to sit confirmed with the card only
    authorized until the hold lapsed about 7 days later. After
    ORDER_SUPPLIER_STALL_HOURS it is compensated instead: the hold is released
    (the customer is never charged), stock is returned, and supplier-service
    withdraws any unpaid CJ order on the resulting order.cancelled.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(
        hours=resources.settings.ORDER_SUPPLIER_STALL_HOURS
    )
    async with resources.database.transaction() as session:
        saga_repository = OrderSagaRepository(session)
        stalled = await saga_repository.get_stalled_supplier_orders_for_update(cutoff)
        if not stalled:
            return 0
        service = _order_service(session, saga_repository)
        for saga, order in stalled:
            resources.logger.warning(
                "Cancelling order %s: CJ did not take it on within %s hours",
                order.id,
                resources.settings.ORDER_SUPPLIER_STALL_HOURS,
            )
            await service._cancel_locked(
                order,
                saga,
                f"CJ did not accept the order within "
                f"{resources.settings.ORDER_SUPPLIER_STALL_HOURS} hours",
            )
        return len(stalled)


def _order_service(session, saga_repository: OrderSagaRepository) -> OrderService:
    return OrderService(
        repository=OrderRepository(session),
        order_item_service=OrderItemService(OrderItemRepository(session)),
        order_address_service=OrderAddressService(OrderAddressRepository(session)),
        outbox_event_service=OutboxEventService(
            OutboxRepository(session=session, model=OutboxEvent)
        ),
        saga_repository=saga_repository,
        production_repository=CustomProductionJobRepository(session),
    )


async def alert_stale_authorizations(resources) -> int:
    """Log every confirmed order whose card hold is close to expiring uncaptured."""
    cutoff = datetime.now(timezone.utc) - timedelta(
        hours=resources.settings.PAYMENT_CAPTURE_ALERT_HOURS
    )
    async with resources.database.transaction() as session:
        stale = await OrderSagaRepository(session).get_stale_uncaptured(cutoff)
    for saga in stale:
        resources.logger.critical(
            "PAYMENT CAPTURE OVERDUE for order %s: card still %s after %d hours; "
            "the authorization expires about 7 days after checkout",
            saga.order_id,
            saga.payment_status,
            resources.settings.PAYMENT_CAPTURE_ALERT_HOURS,
        )
    return len(stale)


async def main() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    next_capture_check = 0.0
    async with order_outbox_resources() as resources:
        while not stop.is_set():
            count = await expire_once(resources)
            if count:
                resources.logger.warning("Cancelled %d timed-out order Sagas", count)
            stalled = await cancel_stalled_supplier_orders(resources)
            if stalled:
                resources.logger.warning("Cancelled %d orders CJ never took on", stalled)
            # Hourly is plenty against a multi-day window, and keeps the alert
            # from repeating every loop.
            if loop.time() >= next_capture_check:
                await alert_stale_authorizations(resources)
                next_capture_check = loop.time() + 3600
            try:
                await asyncio.wait_for(stop.wait(), timeout=30)
            except TimeoutError:
                pass


if __name__ == "__main__":
    asyncio.run(main())
