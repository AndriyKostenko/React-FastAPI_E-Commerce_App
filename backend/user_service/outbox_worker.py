"""Dedicated transactional-outbox relay process for user-service."""

import asyncio
import signal

from service_layer.outbox_poller_service import build_outbox_relay
from outbox_runtime import user_outbox_runtime
from resources import logger


async def main() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    async with user_outbox_runtime() as resources:
        relay = build_outbox_relay(
            session_manager=resources.database,
            publisher=resources.publisher,
            settings=resources.settings,
            logger=resources.logger,
        )
        await relay.run(stop_event)
    logger.info("User outbox worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
