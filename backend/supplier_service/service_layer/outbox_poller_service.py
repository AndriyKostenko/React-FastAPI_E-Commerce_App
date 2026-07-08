from typing import Any
from logging import Logger
from asyncio import sleep

from shared.settings import Settings
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.shared_instances import logger, settings, supplier_service_database_session_manager
from exceptions.outbox_event_exceptions import OutboxEventNotFoundError
from service_layer.outbox_event_service import OutboxEventService
from event_publisher.supplier_event_publisher import supplier_event_publisher, SupplierEventPublisher
from shared.database_layer.outbox_repository import OutboxRepository
from shared.enums.event_enums import SupplierEvents


class OutboxPollerService:
    """Poll unprocessed events from the outbox table and publish them to RabbitMQ."""

    def __init__(self) -> None:
        self.session_manager: DatabaseSessionManager = supplier_service_database_session_manager
        self.supplier_event_publisher: SupplierEventPublisher = supplier_event_publisher
        self.logger: Logger = logger
        self.settings: Settings = settings

    async def event_type_to_publisher(self, event_data: dict[str, Any]) -> None:
        """Route event to the appropriate publisher method."""
        event_type = event_data.get("event_type")
        match event_type:
            case SupplierEvents.SUPPLIER_PRODUCTS_FETCHED:
                await self.supplier_event_publisher.publish_supplier_products_fetched(event_data)
            case _:
                self.logger.warning(f"Unhandled event type in OutboxPollerService: {event_type}")

    async def poll_and_publish(self) -> None:
        """Poll unprocessed events and publish them to the message broker."""
        async with self.session_manager.transaction() as session:
            outbox_event_service = OutboxEventService(repository=OutboxRepository(session=session))
            try:
                unprocessed_events = await outbox_event_service.get_unprocessed_events()
            except OutboxEventNotFoundError:
                self.logger.debug("No unprocessed events found during outbox polling.")
                return
            for event in unprocessed_events:
                try:
                    await self.event_type_to_publisher(event_data=event.payload)
                    await outbox_event_service.mark_event_as_processed(event_id=event.id)
                    self.logger.info(f"Successfully published and marked outbox event as processed: {event.id}")
                except Exception as error:
                    self.logger.error(f"Failed to publish outbox event {event.id}: {error}")

    async def start_outbox_poller(self) -> None:
        """Start an outbox polling loop every N seconds."""
        while True:
            try:
                await self.poll_and_publish()
            except Exception as error:
                self.logger.error(f"Outbox poller service error: {error}")
            await sleep(self.settings.POLLING_INTERVAL_FROM_DB)
