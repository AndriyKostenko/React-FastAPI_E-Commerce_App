from logging import Logger
from typing import Any

from faststream.rabbit import RabbitExchange

from shared.shared_instances import logger, settings, rabbitmq_broker, supplier_exchange
from shared.events.event_publisher import BaseEventPublisher
from shared.settings import Settings
from shared.schemas.event_schemas import SupplierProductsFetchedEvent
from shared.enums.event_enums import SupplierEvents


class SupplierEventPublisher(BaseEventPublisher):
    """Event publisher for supplier_service using FastStream."""

    def __init__(self, logger: Logger, settings: Settings):
        super().__init__(rabbitmq_broker, logger, settings)
        self.exchange: RabbitExchange = supplier_exchange

    async def publish_supplier_products_fetched(self, event_data: dict[str, Any]) -> None:
        """Publish a SupplierProductsFetched event to RabbitMQ."""
        event = SupplierProductsFetchedEvent(**event_data)
        await self.publish_an_event(
            event=event,
            exchange=self.exchange,
            routing_key=SupplierEvents.SUPPLIER_PRODUCTS_FETCHED,
        )
        self.logger.info(f"Published supplier products fetched event for supplier: {event.supplier_id}, fetch_id: {event.fetch_id}")


supplier_event_publisher = SupplierEventPublisher(logger=logger, settings=settings)
