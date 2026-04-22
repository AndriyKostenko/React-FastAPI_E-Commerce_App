from typing import Any
from logging import Logger
from asyncio import sleep

from shared.settings import Settings
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.shared_instances import logger, settings, payment_service_database_session_manager
from exceptions.outbox_event_exceptions import OutboxEventNotFoundError
from service_layer.outbox_event_service import OutboxEventService
from events_publisher.payment_event_publisher import payment_event_publisher, PaymentEventPublisher
from shared.database_layer.outbox_repository import OutboxRepository
from shared.enums.event_enums import PaymentEvents


class OutboxPollerService:
    """Polls unprocessed payment outbox events and publishes them to RabbitMQ."""

    def __init__(self) -> None:
        self.session_manager: DatabaseSessionManager = payment_service_database_session_manager
        self.payment_event_publisher: PaymentEventPublisher = payment_event_publisher
        self.logger: Logger = logger
        self.settings: Settings = settings

    async def event_type_to_publisher(self, event_data: dict[str, Any]) -> None:
        """Route an outbox event to the appropriate publisher method."""
        event_type = event_data.get("event_type")
        match event_type:
            case PaymentEvents.PAYMENT_SUCCEEDED:
                await self.payment_event_publisher.publish_payment_succeeded(event_data)
            case PaymentEvents.PAYMENT_FAILED:
                await self.payment_event_publisher.publish_payment_failed(event_data)
            case _:
                self.logger.warning(f"Unhandled event type in OutboxPollerService: {event_type}")

    async def poll_and_publish(self) -> None:
        """
        Poll unprocessed events from the DB and publish to RabbitMQ.

        Events are marked as processed ONLY after a successful publish so that
        any publish failure leaves the event eligible for retry on the next poll.
        """
        async with self.session_manager.transaction() as session:
            outbox_event_service = OutboxEventService(repository=OutboxRepository(session=session))
            try:
                unprocessed_events = await outbox_event_service.get_unprocessed_events()
            except OutboxEventNotFoundError:
                self.logger.debug("No unprocessed payment outbox events found.")
                return

            for event in unprocessed_events:
                try:
                    await self.event_type_to_publisher(event_data=event.payload)
                    await outbox_event_service.mark_event_as_processed(event_id=event.id)
                    self.logger.info(f"Published and marked payment outbox event as processed: {event.id}")
                except Exception as error:
                    self.logger.error(f"Failed to publish payment outbox event {event.id}: {error}")

    async def start_outbox_poller(self) -> None:
        """Run the outbox poller on a fixed interval."""
        while True:
            try:
                await self.poll_and_publish()
            except Exception as error:
                self.logger.error(f"Payment outbox poller error: {error}")
            await sleep(self.settings.POLLING_INTERVAL_FROM_DB)
