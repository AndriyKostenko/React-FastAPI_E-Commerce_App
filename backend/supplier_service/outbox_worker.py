"""Dedicated transactional-outbox relay process for supplier-service."""

from resources import logger, supplier_outbox_resources
from service_layer.outbox_poller_service import build_outbox_relay
from shared.outbox import run_outbox_worker


if __name__ == "__main__":
    run_outbox_worker(supplier_outbox_resources, build_outbox_relay, logger=logger)
