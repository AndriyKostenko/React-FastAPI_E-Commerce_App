from logging import Logger
from typing import Any

from shared.shared_instances import (
    logger,
    cart_event_idempotency_service,
    cart_service_database_session_manager,
)
from shared.enums.event_enums import OrderEvents
from shared.schemas.event_schemas import OrderCreatedEvent, OrderConfirmedEvent
from database_layer.cart_repository import CartRepository
from service_layer.cart_services import CartService


class CartEventConsumer:
    """
    Consumes domain events that affect the shopping cart.

    Currently handles:
    - order.created: clears the user's cart after an order is placed.
    - order.confirmed: idempotent safety-net clear in case the cart was not
      already emptied when the order was created.
    """

    def __init__(self, logger: Logger) -> None:
        self.logger: Logger = logger
        self.idempotency_service = cart_event_idempotency_service

    async def _get_cart_service(self):
        """Create a CartService with a fresh database session."""
        async with cart_service_database_session_manager.transaction() as session:
            yield CartService(repository=CartRepository(session=session))

    async def handle_order_event(self, message: dict[str, Any]) -> None:
        """Route order events to the appropriate handler."""
        event_type = message.get("event_type")

        match event_type:
            case OrderEvents.ORDER_CREATED:
                await self.handle_order_created(message)
            case OrderEvents.ORDER_CONFIRMED:
                await self.handle_order_confirmed(message)
            case _:
                self.logger.warning(f"Unhandled cart consumer event type: {event_type}")

    async def handle_order_created(self, message: dict[str, Any]) -> None:
        """
        Clear the user's cart once an order has been created.

        This follows the standard e-commerce flow: the cart is emptied when the
        customer places an order. If downstream SAGA steps fail (inventory or
        payment), the order service handles compensation; the cart remains clear.
        """
        event = OrderCreatedEvent(**message)

        try:
            claimed = await self.idempotency_service.try_claim_event(
                event_id=event.event_id,
                event_type=event.event_type,
            )
            if not claimed:
                self.logger.info(
                    f"Skipping duplicate order.created event for cart — order: {event.order_id}"
                )
                return

            self.logger.info(
                f"Clearing cart for user {event.user_id} after order {event.order_id}"
            )

            async for cart_service in self._get_cart_service():
                await cart_service.clear_cart(user_id=event.user_id)

            await self.idempotency_service.mark_event_as_processed(
                event_id=event.event_id,
                event_type=event.event_type,
                order_id=event.order_id,
                result="cart_cleared",
            )
            self.logger.info(
                f"Cart cleared for user {event.user_id} after order {event.order_id}"
            )

        except Exception as e:
            await self.idempotency_service.release_claim(
                event_id=event.event_id,
                event_type=event.event_type,
            )
            self.logger.error(
                f"Error clearing cart for order {message.get('order_id')}: {e}"
            )
            raise

    async def handle_order_confirmed(self, message: dict[str, Any]) -> None:
        """
        Idempotent safety-net: ensure the cart is empty when an order is confirmed.

        order.created should already have cleared the cart; this handler catches
        any edge cases where the confirmation event is received first or the
        initial clear failed.
        """
        event = OrderConfirmedEvent(**message)

        try:
            claimed = await self.idempotency_service.try_claim_event(
                event_id=event.event_id,
                event_type=event.event_type,
            )
            if not claimed:
                self.logger.info(
                    f"Skipping duplicate order.confirmed event for cart — order: {event.order_id}"
                )
                return

            self.logger.info(
                f"Ensuring cart is cleared for user {event.user_id} on order confirmation {event.order_id}"
            )

            async for cart_service in self._get_cart_service():
                await cart_service.clear_cart(user_id=event.user_id)

            await self.idempotency_service.mark_event_as_processed(
                event_id=event.event_id,
                event_type=event.event_type,
                order_id=event.order_id,
                result="cart_cleared_on_confirmation",
            )

        except Exception as e:
            await self.idempotency_service.release_claim(
                event_id=event.event_id,
                event_type=event.event_type,
            )
            self.logger.error(
                f"Error clearing cart on order confirmation {message.get('order_id')}: {e}"
            )
            raise


cart_event_consumer = CartEventConsumer(logger=logger)
