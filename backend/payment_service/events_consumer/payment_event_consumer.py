from typing import Any
from logging import Logger

from shared.shared_instances import logger, payment_service_database_session_manager
from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.shared_instances import payment_event_idempotency_service
from shared.enums.event_enums import OrderEvents
from shared.schemas.event_schemas import OrderCancelledEvent
from database_layer.payment_repository import PaymentRepository
from shared.database_layer.outbox_repository import OutboxRepository
from service_layer.payment_service import PaymentService
from service_layer.outbox_event_service import OutboxEventService
from shared.shared_instances import settings
from shared.settings import Settings


class PaymentEventConsumer:
    """
    Consumes order events that require payment action.

    Currently handles:
    - order.cancelled: triggers a Stripe refund when a payment was already succeeded.
    """

    def __init__(self, logger: Logger, settings: Settings) -> None:
        self.logger: Logger = logger
        self.settings: Settings = settings
        self.idempotency_service: IdempotencyEventService = payment_event_idempotency_service

    async def _get_payment_service(self):
        """Create a PaymentService with a fresh DB session (mirrors FastAPI DI for consumers)."""
        async with payment_service_database_session_manager.transaction() as session:
            outbox_service = OutboxEventService(repository=OutboxRepository(session=session))
            payment_service = PaymentService(
                repository=PaymentRepository(session=session),
                outbox_event_service=outbox_service,
                settings=self.settings,
                logger=self.logger,
            )
            yield payment_service

    async def handle_payment_event(self, message: dict[str, Any]) -> None:
        event_type = message.get("event_type")
        match event_type:
            case OrderEvents.ORDER_CANCELLED:
                await self.handle_order_cancelled(message)
            case _:
                self.logger.warning(f"Unhandled payment consumer event type: {event_type}")

    async def handle_order_cancelled(self, message: dict[str, Any]) -> None:
        """
        When an order is cancelled, issue a Stripe refund if a payment was already succeeded.

        Steps:
        1. Parse the event and guard against duplicates.
        2. Look up the payment by order_id.
        3. If payment status is 'succeeded', call PaymentService.refund_payment().
        4. Mark event as processed.
        """
        event = OrderCancelledEvent(**message)

        try:
            claimed = await self.idempotency_service.try_claim_event(
                event_id=event.event_id,
                event_type=event.event_type,
            )
            if not claimed:
                self.logger.info(f"Duplicate order.cancelled event received and already processed — order: {event.order_id}")
                return

            self.logger.info(f"Processing order.cancelled for potential refund — order: {event.order_id}")

            async for payment_service in self._get_payment_service():
                _ = await payment_service.handle_payment_refund(order_id=event.order_id)

            self.logger.info(f"Refund processed for order: {event.order_id}")

            await self.idempotency_service.mark_event_as_processed(
                event_id=event.event_id,
                event_type=event.event_type,
                order_id=event.order_id,
                result="refunded",
            )

        except Exception as e:
            await self.idempotency_service.release_claim(event_id=event.event_id, event_type=event.event_type)
            self.logger.error(f"Error handling order.cancelled for order {message.get('order_id')}: {e}")
            raise


payment_event_consumer = PaymentEventConsumer(logger=logger, settings=settings)
