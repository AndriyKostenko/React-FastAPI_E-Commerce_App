"""Dedicated transactional-outbox relay process for order-service."""

import asyncio
import signal

from service_layer.outbox_poller_service import build_outbox_relay
from resources import order_outbox_resources


async def main() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    async with order_outbox_resources() as resources:
        try:
            await build_outbox_relay(resources).run(stop_event)
        finally:
            resources.logger.info("Order outbox worker stopping")


if __name__ == "__main__":
    asyncio.run(main())
