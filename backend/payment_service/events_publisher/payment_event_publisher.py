from typing import Any
from logging import Logger

from faststream.rabbit import RabbitBroker, RabbitExchange

from shared.settings import Settings
from shared.events.event_publisher import BaseEventPublisher
from messaging import payment_exchange
from shared.contracts.events import PaymentSucceededEvent, PaymentFailedEvent, PaymentRefundedEvent, PaymentCancelledEvent


class PaymentEventPublisher(BaseEventPublisher):
    """Event publisher for Payment Service using FastStream / RabbitMQ."""

    def __init__(
        self,
        rabbitmq_broker: RabbitBroker,
        logger: Logger,
        settings: Settings,
    ) -> None:
        super().__init__(rabbitmq_broker, logger, settings)
        self.payment_exchange: RabbitExchange = payment_exchange

    async def publish_payment_succeeded(self, event_data: dict[str, Any]) -> None:
        """Publish payment.succeeded — consumed by order service, notification service, etc."""
        event = PaymentSucceededEvent(**event_data)
        await self.publish_an_event(
            event=event,
            exchange=self.payment_exchange,
            routing_key=event.event_type,
        )
        self.logger.info(f"Published PaymentSucceededEvent for order {event.order_id}")

    async def publish_payment_failed(self, event_data: dict[str, Any]) -> None:
        """Publish payment.failed — triggers order cancellation and optionally a notification."""
        event = PaymentFailedEvent(**event_data)
        await self.publish_an_event(
            event=event,
            exchange=self.payment_exchange,
            routing_key=event.event_type,
        )
        self.logger.info(f"Published PaymentFailedEvent for order {event.order_id}: {event.reason}")

    async def publish_payment_refunded(self, event_data: dict[str, Any]) -> None:
        """Publish payment.refunded — consumed by order service and notification service."""
        event = PaymentRefundedEvent(**event_data)
        await self.publish_an_event(
            event=event,
            exchange=self.payment_exchange,
            routing_key=event.event_type,
        )
        self.logger.info(f"Published PaymentRefundedEvent for order {event.order_id}")

    async def publish_payment_cancelled(self, event_data: dict[str, Any]) -> None:
        """Publish payment.cancelled — consumed by order service to cancel the order."""
        event = PaymentCancelledEvent(**event_data)
        await self.publish_an_event(
            event=event,
            exchange=self.payment_exchange,
            routing_key=event.event_type,
        )
        self.logger.info(f"Published PaymentCancelledEvent for order {event.order_id}: {event.reason}")
