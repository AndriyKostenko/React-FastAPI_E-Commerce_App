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
        item_service = OrderItemService(OrderItemRepository(session))
        service = OrderService(
            repository=OrderRepository(session),
            order_item_service=item_service,
            order_address_service=OrderAddressService(OrderAddressRepository(session)),
            outbox_event_service=OutboxEventService(
                OutboxRepository(session=session, model=OutboxEvent)
            ),
            saga_repository=saga_repository,
            production_repository=CustomProductionJobRepository(session),
        )
        for saga, order in expired:
            await service._cancel_locked(
                order,
                saga,
                "Order Saga timed out before payment and inventory completed",
            )
        return len(expired)


async def main() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    async with order_outbox_resources() as resources:
        while not stop.is_set():
            count = await expire_once(resources)
            if count:
                resources.logger.warning("Cancelled %d timed-out order Sagas", count)
            try:
                await asyncio.wait_for(stop.wait(), timeout=30)
            except TimeoutError:
                pass


if __name__ == "__main__":
    asyncio.run(main())
