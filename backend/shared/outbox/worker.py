"""Process scaffolding shared by every service's transactional-outbox worker.

Each service owns its resource graph (``*OutboxResources``) and its event
routing (``build_outbox_relay``).  The signal wiring, the ``asyncio`` entry
point, and the "open resources -> poll until SIGTERM -> unwind" lifecycle are
identical everywhere and live here.
"""

from asyncio import Event, get_running_loop, run
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from logging import Logger
from signal import SIGINT, SIGTERM
from typing import TypeVar

from shared.outbox.relay import OutboxRelay


ResourcesT = TypeVar("ResourcesT")

RuntimeFactory = Callable[[], AbstractAsyncContextManager[ResourcesT]]
RelayFactory = Callable[[ResourcesT], OutboxRelay]


async def run_relay_worker(
    runtime: AbstractAsyncContextManager[ResourcesT],
    build_relay: RelayFactory[ResourcesT],
    *,
    logger: Logger | None = None,
) -> None:
    """Open ``runtime``, relay its outbox until SIGINT/SIGTERM, then unwind.

    ``runtime`` is an already-constructed async context manager whose entered
    value is passed straight to ``build_relay``.
    """
    stop_event = Event()
    loop = get_running_loop()
    for sig in (SIGINT, SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    try:
        async with runtime as resources:
            await build_relay(resources).run(stop_event)
    finally:
        if logger is not None:
            logger.info("Outbox worker stopped")


def run_outbox_worker(
    runtime_factory: RuntimeFactory[ResourcesT],
    build_relay: RelayFactory[ResourcesT],
    *,
    logger: Logger | None = None,
) -> None:
    """Synchronous ``__main__`` entry point for a dedicated outbox process."""
    run(run_relay_worker(runtime_factory(), build_relay, logger=logger))
