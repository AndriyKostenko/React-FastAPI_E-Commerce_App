from typing import Any
from logging import Logger
from asyncio import sleep

from shared.settings import Settings
from shared.database_setup import DatabaseSessionManager
from shared.shared_instances import logger, settings, order_service_database_session_manager
from exceptions.outbox_event_exceptions import OutboxEventNotFoundError
from service_layer.outbox_event_service import OutboxEventService
from events_publisher.order_event_publisher import order_event_publisher, OrderEventPublisher
from database_layer.outbox_repository import OutboxRepository
from shared.enums.event_enums import OrderEvents, InventoryEvents


class OutboxPollerService:
    """Service for polling unprocessed events from the outbox table and publishing them to the message broker"""
    def __init__(self) -> None:
        self.session_manager: DatabaseSessionManager = order_service_database_session_manager
        self.order_event_publisher: OrderEventPublisher = order_event_publisher
        self.logger: Logger = logger
        self.settings: Settings = settings

    async def event_type_to_publisher(self, event_data: dict[str, Any]):
        event_type = event_data.get("event_type")
        match event_type:
            case OrderEvents.ORDER_CREATED:
                await self.order_event_publisher.publish_order_created(event_data)
            case InventoryEvents.INVENTORY_RESERVE_REQUESTED:
                await self.order_event_publisher.publish_inventory_reserve_requested(event_data)
            case _:
                self.logger.warning(f"Unhandeled event type in OutboxPollerService: {event_type}")

    async def poll_and_publish(self) -> None:
        """
        Creating its own session for each poll to avoid conflicts with the main application sessions.
        Polling unprocessed events and publish them to the message broker
        """
        async with self.session_manager.transaction() as session: # fresh session from pool
            outbox_event_service = OutboxEventService(repository=OutboxRepository(session=session))
            try:
                unprocessed_events = await outbox_event_service.get_unprocessed_events()
            except OutboxEventNotFoundError:
                self.logger.debug("No unprocessed events found during outbox polling.")
                # nothing to process, continue
                return
            for event in unprocessed_events:
                try:
                    await self.event_type_to_publisher(event_data=event.payload)
                    await outbox_event_service.mark_event_as_processed(event_id=event.id)
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
