from typing import Any
from logging import Logger
from asyncio import sleep

from shared.logger_config import
from shared.settings import Settings
from shared.shared_instances import logger, settings
from exceptions.outbox_event_exceptions import OutboxEventNotFoundError
from service_layer.outbox_event_service import outbox_event_service, OutboxEventService
from events_publisher.order_event_publisher import order_event_publisher, OrderEventPublisher
from shared.schemas.event_schemas import OrderCreatedEvent, InventoryReserveRequested


class OutboxPollerService:
    def __init__(self) -> None:
        self.outbox_event_service: OutboxEventService = outbox_event_service
        self.order_event_publisher: OrderEventPublisher = order_event_publisher
        self.logger: Logger = logger
        self.settings: Settings = settings

    async def event_type_to_publisher(self, event_data: dict[str, Any]):
        event_type = event_data.get("event_type")
        match event_type:
            case "order.created":
                await self.order_event_publisher.publish_order_created(event_data)
            case "inventory.reserve.requested":
                await self.order_event_publisher.publish_inventory_reserve_requested(event_data)

    async def poll_and_publish(self) -> None:
        try:
            unprocessed_events = await self.outbox_event_service.get_unprocessed_events()
        except OutboxEventNotFoundError as error:
            self.logger.error(f"Error while getting an unprocessed events: {error}")
            # nothing to process, continue
            return
        for event in unprocessed_events:
            try:
                await self.event_type_to_publisher(event_data=event.payload)
                await self.outbox_event_service.mark_event_as_processed(event_id=event.id)
            except Exception as error:
                self.logger.error(f"An error is occured during outbox event processing: {error}")

    async def start_outbox_poller(self):
        """Starting an outbox polling every 500ms"""
        while True:
            try:
                await self.poll_and_publish()
            except Exception as error:
                self.logger.error(f"Outbox poller service error: {error}")
            await sleep(self.settings.POLLING_INTERVAL_FROM_DB)

outbox_poller_service = OutboxPollerService()
