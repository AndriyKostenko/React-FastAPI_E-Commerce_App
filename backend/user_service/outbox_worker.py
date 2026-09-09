"""Dedicated transactional-outbox relay process for user-service."""

from managers import OutboxManager, logger
from service_layer.outbox_poller_service import build_outbox_relay
from shared.outbox import run_outbox_worker


if __name__ == "__main__":
    run_outbox_worker(OutboxManager, build_outbox_relay, logger=logger)
