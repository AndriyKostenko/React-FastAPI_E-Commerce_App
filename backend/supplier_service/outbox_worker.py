"""Dedicated transactional-outbox relay process for supplier-service."""

import asyncio
import signal

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange

from resources import logger, settings, supplier_outbox_resources
from service_layer.outbox_poller_service import build_outbox_relay


async def main() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    broker = RabbitBroker(url=settings.RABBITMQ_BROKER_URL)
    supplier_exchange = RabbitExchange(
        name="supplier.events.exchange", durable=True, type=ExchangeType.TOPIC
    )
    order_exchange = RabbitExchange(
        name="order.events.exchange", durable=True, type=ExchangeType.TOPIC
    )
    inventory_exchange = RabbitExchange(
        name="inventory.events.exchange", durable=True, type=ExchangeType.TOPIC
    )
    async with supplier_outbox_resources(
        broker=broker,
        supplier_exchange=supplier_exchange,
        order_exchange=order_exchange,
        inventory_exchange=inventory_exchange,
    ) as resources:
        relay = build_outbox_relay(
            database=resources.database,
            publisher=resources.publisher,
            logger=resources.logger,
            poll_interval=float(resources.settings.POLLING_INTERVAL_FROM_DB),
        )
        await relay.run(stop_event)
    logger.info("Supplier outbox worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
