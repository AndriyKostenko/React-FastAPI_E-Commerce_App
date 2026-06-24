from logging import Logger
from typing import Any

from shared.shared_instances import (
    logger,
    shipping_event_idempotency_service,
    shipping_service_database_session_manager,
)
from shared.enums.event_enums import OrderEvents
from shared.schemas.event_schemas import OrderConfirmedEvent, OrderCancelledEvent
from database_layer.shipping_repository import ShipmentRepository, ShippingMethodRepository
from service_layer.shipment_service import ShipmentService


class ShippingEventConsumer:
    """Consumes order lifecycle events and manages shipments."""

    def __init__(self, logger: Logger):
        self.logger: Logger = logger
        self.idempotency_service = shipping_event_idempotency_service

    async def _get_shipment_service(self):
        """Create a ShipmentService with a fresh database session."""
        async with shipping_service_database_session_manager.transaction() as session:
            yield ShipmentService(
                shipment_repository=ShipmentRepository(session=session),
                method_repository=ShippingMethodRepository(session=session),
            )

    async def handle_order_event(self, message: dict[str, Any]) -> None:
        """Route order events to the appropriate handler."""
        event_type = message.get("event_type")

        match event_type:
            case OrderEvents.ORDER_CONFIRMED:
                await self.handle_order_confirmed(message)
            case OrderEvents.ORDER_CANCELLED:
                await self.handle_order_cancelled(message)
            case _:
                self.logger.warning(f"Unhandled shipping consumer event type: {event_type}")

    async def handle_order_confirmed(self, message: dict[str, Any]) -> None:
        """Create a shipment when an order is confirmed."""
        event = OrderConfirmedEvent(**message)

        try:
            claimed = await self.idempotency_service.try_claim_event(
                event_id=event.event_id,
                event_type=event.event_type,
            )
            if not claimed:
                self.logger.info(f"Skipping duplicate order.confirmed event for shipping — order: {event.order_id}")
                return

            self.logger.info(f"Creating shipment for order {event.order_id}")

            async for shipment_service in self._get_shipment_service():
                # For now, pick the cheapest active method. In production this could come from the order event.
                methods = await shipment_service.method_repository.get_active_methods()
                if not methods:
                    self.logger.warning(f"No active shipping methods available for order {event.order_id}")
                    result = "no_active_methods"
                    break

                method = methods[0]
                await shipment_service.create_shipment_from_order_event(
                    order_id=event.order_id,
                    user_id=event.user_id,
                    user_email=event.user_email,
                    method_id=method.id,
                )
                result = "shipment_created"

            await self.idempotency_service.mark_event_as_processed(
                event_id=event.event_id,
                event_type=event.event_type,
                order_id=event.order_id,
                result=result,
            )
            self.logger.info(f"Shipment processed for order {event.order_id}")

        except Exception as e:
            await self.idempotency_service.release_claim(
                event_id=event.event_id,
                event_type=event.event_type,
            )
            self.logger.error(f"Error creating shipment for order {message.get('order_id')}: {e}")
            raise

    async def handle_order_cancelled(self, message: dict[str, Any]) -> None:
        """Cancel the shipment when an order is cancelled."""
        event = OrderCancelledEvent(**message)

        try:
            claimed = await self.idempotency_service.try_claim_event(
                event_id=event.event_id,
                event_type=event.event_type,
            )
            if not claimed:
                self.logger.info(f"Skipping duplicate order.cancelled event for shipping — order: {event.order_id}")
                return

            self.logger.info(f"Cancelling shipment for order {event.order_id}")

            result = "no_shipment_found"
            async for shipment_service in self._get_shipment_service():
                cancelled = await shipment_service.cancel_shipment_by_order_id(
                    order_id=event.order_id,
                    reason=event.reason,
                    user_email=event.user_email,
                )
                if cancelled:
                    result = "shipment_cancelled"

            await self.idempotency_service.mark_event_as_processed(
                event_id=event.event_id,
                event_type=event.event_type,
                order_id=event.order_id,
                result=result,
            )
            self.logger.info(f"Shipment cancellation processed for order {event.order_id}")

        except Exception as e:
            await self.idempotency_service.release_claim(
                event_id=event.event_id,
                event_type=event.event_type,
            )
            self.logger.error(f"Error cancelling shipment for order {message.get('order_id')}: {e}")
            raise


shipping_event_consumer = ShippingEventConsumer(logger=logger)
