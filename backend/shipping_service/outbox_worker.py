import asyncio
import signal

from resources import shipping_outbox_runtime
from service_layer.outbox_poller_service import build_outbox_relay


async def main() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    async with shipping_outbox_runtime() as resources:
        await build_outbox_relay(
            resources.database,
            resources.event_publisher,
            resources.logger,
            float(resources.settings.POLLING_INTERVAL_FROM_DB),
        ).run(stop)


if __name__ == "__main__":
    asyncio.run(main())
