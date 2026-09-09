from typing import Any
from logging import Logger

from faststream.rabbit import RabbitBroker, RabbitExchange

from shared.settings import Settings
from shared.events.event_publisher import BaseEventPublisher
from messaging import inventory_exchange, order_exchange
from shared.contracts.events import (
    ArtworkReleasedEvent,
    ArtworkRetainedEvent,
    OrderCreatedEvent,
    OrderCancelledEvent,
    OrderConfirmedEvent,
    InventoryReserveRequested,
    InventoryReleaseRequested,
    ProductionJobCancelledEvent,
    ProductionJobDeliveredEvent,
    ProductionJobPrintedEvent,
    ProductionJobShippedEvent,
    ProductionJobStartedEvent,
)


class OrderEventPublisher(BaseEventPublisher):
    """Event publisher for Order Service using FastStream"""
    def __init__(
        self,
        rabbitmq_broker: RabbitBroker,
        logger: Logger,
        settings: Settings,
    ) -> None:
        super().__init__(rabbitmq_broker, logger, settings)
        self.order_exchange: RabbitExchange = order_exchange
        self.inventory_exchange: RabbitExchange = inventory_exchange

    async def publish_order_created(self, event_data: dict[str, Any]):
        """Publish order created event (SAGA start)"""
        event = OrderCreatedEvent(**event_data)
        await self.publish_an_event(event=event, exchange=self.order_exchange, routing_key=event.event_type)
        self.logger.info(f"Published OrderCreatedEvent for order {event.order_id}")

    async def publish_inventory_reserve_requested(self, event_data: dict[str, Any]):
        """Request inventory reservation from Product Service"""
        event = InventoryReserveRequested(**event_data)
        await self.publish_an_event(event=event, exchange=self.inventory_exchange, routing_key=event.event_type)
        self.logger.info(f"Published InventoryReserveRequested for order: {event.order_id}")

    async def publish_order_confirmed(self, event_data: dict[str, Any]):
        """Publish order confirmed event (SAGA success)"""
        event = OrderConfirmedEvent(**event_data)
        await self.publish_an_event(event=event, exchange=self.order_exchange, routing_key=event.event_type)
        self.logger.info(f"Published OrderConfirmedEvent for order {event.order_id}")

    async def publish_order_cancelled(self, event_data: dict[str, Any]):
        """Publish order cancelled event (SAGA compensation)"""
        event = OrderCancelledEvent(**event_data)
        await self.publish_an_event(event=event, exchange=self.order_exchange, routing_key=event.event_type)
        self.logger.info(f"Published OrderCancelledEvent for order: {event.order_id}: {event.reason}")

    async def publish_inventory_release_requested(self, event_data: dict[str, Any]):
        """Request inventory release (compensation transaction)"""
        event = InventoryReleaseRequested(**event_data)
        await self.publish_an_event(event=event, exchange=self.inventory_exchange, routing_key=event.event_type)
        self.logger.info(f"Published InventoryReleaseRequested for order: {event.order_id}: {event.reason}")

    async def publish_production_job_started(self, event_data: dict[str, Any]):
        """Publish that a queued garment is now at the press"""
        await self._publish_production_event(ProductionJobStartedEvent(**event_data))

    async def publish_production_job_printed(self, event_data: dict[str, Any]):
        """Publish that a garment is printed and awaiting post"""
        await self._publish_production_event(ProductionJobPrintedEvent(**event_data))

    async def publish_production_job_shipped(self, event_data: dict[str, Any]):
        """Publish that an in-house parcel is in the post, with its tracking number"""
        await self._publish_production_event(ProductionJobShippedEvent(**event_data))

    async def publish_production_job_delivered(self, event_data: dict[str, Any]):
        """Publish that an in-house parcel reached the customer"""
        await self._publish_production_event(ProductionJobDeliveredEvent(**event_data))

    async def publish_production_job_cancelled(self, event_data: dict[str, Any]):
        """Publish that a job left the queue without being fulfilled"""
        await self._publish_production_event(ProductionJobCancelledEvent(**event_data))

    async def _publish_production_event(self, event) -> None:
        """Send one in-house fulfillment event on the shared order exchange.

        The "production.job.*" routing key matches neither the "order.#" nor
        the "cj.order.*" binding, so each interested consumer binds its own
        queue and the three fulfillment flows stay independently retryable.
        """
        await self.publish_an_event(
            event=event, exchange=self.order_exchange, routing_key=event.event_type
        )
        self.logger.info(
            f"Published {event.event_type} for production job {event.job_id} "
            f"(order {event.order_id})"
        )

    async def publish_artwork_retained(self, event_data: dict[str, Any]):
        """Tell product_service its stored print files are spoken for"""
        event = ArtworkRetainedEvent(**event_data)
        await self.publish_an_event(event=event, exchange=self.order_exchange, routing_key=event.event_type)
        self.logger.info(f"Published ArtworkRetainedEvent for order {event.order_id}")

    async def publish_artwork_released(self, event_data: dict[str, Any]):
        """Tell product_service an order no longer needs its print files"""
        event = ArtworkReleasedEvent(**event_data)
        await self.publish_an_event(event=event, exchange=self.order_exchange, routing_key=event.event_type)
        self.logger.info(f"Published ArtworkReleasedEvent for order {event.order_id}")
