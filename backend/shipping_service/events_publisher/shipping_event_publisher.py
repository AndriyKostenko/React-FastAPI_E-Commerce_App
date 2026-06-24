from typing import Any
from logging import Logger

from faststream.rabbit import RabbitExchange

from shared.settings import Settings
from shared.events.event_publisher import BaseEventPublisher
from shared.shared_instances import settings, logger, rabbitmq_broker, shipping_exchange
from shared.schemas.event_schemas import (
    ShipmentCreatedEvent,
    ShipmentShippedEvent,
    ShipmentDeliveredEvent,
    ShipmentCancelledEvent,
)


class ShippingEventPublisher(BaseEventPublisher):
    """Event publisher for Shipping Service using FastStream."""

    def __init__(self, logger: Logger, settings: Settings):
        super().__init__(rabbitmq_broker, logger, settings)
        self.shipping_exchange: RabbitExchange = shipping_exchange

    async def publish_shipment_created(self, event_data: dict[str, Any]):
        event = ShipmentCreatedEvent(**event_data)
        await self.publish_an_event(
            event=event,
            exchange=self.shipping_exchange,
            routing_key=event.event_type,
        )
        self.logger.info(f"Published ShipmentCreatedEvent for shipment {event.shipment_id}")

    async def publish_shipment_shipped(self, event_data: dict[str, Any]):
        event = ShipmentShippedEvent(**event_data)
        await self.publish_an_event(
            event=event,
            exchange=self.shipping_exchange,
            routing_key=event.event_type,
        )
        self.logger.info(f"Published ShipmentShippedEvent for shipment {event.shipment_id}")

    async def publish_shipment_delivered(self, event_data: dict[str, Any]):
        event = ShipmentDeliveredEvent(**event_data)
        await self.publish_an_event(
            event=event,
            exchange=self.shipping_exchange,
            routing_key=event.event_type,
        )
        self.logger.info(f"Published ShipmentDeliveredEvent for shipment {event.shipment_id}")

    async def publish_shipment_cancelled(self, event_data: dict[str, Any]):
        event = ShipmentCancelledEvent(**event_data)
        await self.publish_an_event(
            event=event,
            exchange=self.shipping_exchange,
            routing_key=event.event_type,
        )
        self.logger.info(f"Published ShipmentCancelledEvent for shipment {event.shipment_id}")


shipping_event_publisher = ShippingEventPublisher(logger=logger, settings=settings)
