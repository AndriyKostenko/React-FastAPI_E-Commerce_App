from logging import Logger
from typing import Any

from database_layer.order_address_repository import OrderAddressRepository
from database_layer.order_item_repository import OrderItemRepository
from database_layer.order_repository import OrderRepository
from shared.database_layer.outbox_repository import OutboxRepository
from events_publisher.order_event_publisher import order_event_publisher
from service_layer.order_address_service import OrderAddressService
from service_layer.order_item_service import OrderItemService
from shared.schemas.order_schemas import UpdateOrder
from shared.schemas.event_schemas import (
    CJOrderCreatedEvent,
    InventoryReserveFailed,
    InventoryReserveSucceeded,
    PaymentSucceededEvent,
    PaymentFailedEvent,
    PaymentCancelledEvent,
    ShipmentCreatedEvent,
    ShipmentShippedEvent,
    ShipmentDeliveredEvent,
    ShipmentCancelledEvent,
    ConfirmedOrderItem,
    ConfirmedOrderAddress,
)
from shared.shared_instances import logger, order_service_database_session_manager
from service_layer.order_service import OrderService
from shared.enums.status_enums import OrderStatus, OrderDeliveryStatus
from service_layer.outbox_event_service import OutboxEventService
from shared.shared_instances import order_event_idempotency_service
from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.enums.event_enums import InventoryEvents, OrderEvents, PaymentEvents, ShippingEvents
from exceptions.order_exceptions import OrderNotFoundError, OrderNotCancellableError

"""
Order Event Consumer - SAGA Orchestrator
This consumer listens to events from other services (primarily Product Service)
and orchestrates the Order SAGA workflow:

1. When inventory reservation succeeds -> Confirm the order
2. When inventory reservation fails -> Cancel the order and trigger compensation

The FastStream app will be executed via `faststream run`, so no manual uvicorn setup is needed.
"""


class OrderEventConsumer:
    """
    Business logic handler for Order SAGA orchestration.
    This class handles the actual business logic, while the subscriber functions
    handle the FastStream integration.
    """
    def __init__(self, logger: Logger):
        self.logger: Logger = logger
        self.idempotency_service: IdempotencyEventService = order_event_idempotency_service

    async def _get_order_service(self):
        """
        Creating an OrderService instance with a fresh database session.
        This is similar to FastAPI's dependency injection but for FastStream consumers.
        """
        async with order_service_database_session_manager.transaction() as session:
            order_item_service = OrderItemService(
                repository=OrderItemRepository(session=session)
            )
            order_address_service = OrderAddressService(
                repository=OrderAddressRepository(session=session)
            )
            outbox_event_service = OutboxEventService(
                repository=OutboxRepository(session=session)
            )
            order_service = OrderService(
                repository=OrderRepository(session=session),
                order_item_service=order_item_service,
                order_address_service=order_address_service,
                outbox_event_service=outbox_event_service
            )
            yield order_service

    def _build_order_confirmed_event_data(
        self,
        order,
    ) -> dict[str, Any]:
        """Build an OrderConfirmedEvent payload enriched with items and address."""
        event_data: dict[str, Any] = {
            "order_id": str(order.id),
            "user_id": str(order.user_id),
            "user_email": order.user_email,
        }

        if order.items:
            event_data["items"] = [
                ConfirmedOrderItem(
                    product_id=item.product_id,
                    variant_id=item.variant_id,
                    quantity=item.quantity,
                    price=item.price,
                ).model_dump()
                for item in order.items
            ]
        else:
            event_data["items"] = []

        if order.address:
            address = order.address
            event_data["address"] = ConfirmedOrderAddress(
                street=address.street or "",
                city=address.city or "",
                province=address.province or "",
                postal_code=address.postal_code or "",
                country=address.country,
                country_code=address.country_code,
                name=address.name,
                phone=address.phone,
            ).model_dump()

        return event_data

    async def handle_order_saga_response(self, message: dict[str, Any]):
        """
        Route inventory SAGA responses to appropriate handlers based on event type.
        """
        event_type = message.get("event_type")
        match event_type:
            case InventoryEvents.INVENTORY_RESERVE_SUCCEEDED:
                await self.handle_inventory_reserve_succeeded(message)
            case InventoryEvents.INVENTORY_RESERVE_FAILED:
                await self.handle_inventory_reserve_failed(message)
            case _:
                self.logger.warning(f"Unhandled SAGA event type: {event_type}")

   
    async def handle_payment_event(self, message: dict[str, Any]):
        """Route payment events to appropriate handlers based on event type."""
        event_type = message.get("event_type")
        match event_type:
            case PaymentEvents.PAYMENT_SUCCEEDED:
                await self.handle_payment_succeeded(message)
            case PaymentEvents.PAYMENT_FAILED:
                await self.handle_payment_failed(message)
            case PaymentEvents.PAYMENT_CANCELLED:
                await self.handle_payment_cancelled(message)
            case _:
                self.logger.warning(f"Unhandled payment event type in order consumer: {event_type}")

    async def handle_cj_order_created(self, message: dict[str, Any]) -> None:
        """Persist the CJ Dropshipping order number on the local order."""
        try:
            event = CJOrderCreatedEvent(**message)
            claimed = await self.idempotency_service.try_claim_event(
                event_id=event.event_id,
                event_type=event.event_type,
            )
            if not claimed:
                self.logger.info(f"Skipping duplicate cj.order.created event for order: {event.order_id}")
                return

            result = "cj_order_number_updated"
            async for order_service in self._get_order_service():
                try:
                    current_order = await order_service.get_order_by_id(order_id=event.order_id)
                except OrderNotFoundError:
                    self.logger.warning(
                        f"Order {event.order_id} not found for cj.order.created event — skipping"
                    )
                    result = "order_not_found"
                    break

                await order_service.update_order(
                    order_id=event.order_id,
                    order_data=UpdateOrder(
                        amount=current_order.amount,
                        cj_order_number=event.cj_order_number,
                    ),
                )
                self.logger.info(
                    f"Updated order {event.order_id} with CJ order number: {event.cj_order_number}"
                )

            await self.idempotency_service.mark_event_as_processed(
                event_id=event.event_id,
                event_type=event.event_type,
                order_id=event.order_id,
                result=result,
            )
        except Exception as e:
            try:
                if message.get("event_id") and message.get("event_type"):
                    await self.idempotency_service.release_claim(
                        event_id=message["event_id"],
                        event_type=message["event_type"],
                    )
            except Exception:
                pass
            self.logger.error(f"Error handling cj.order.created for order {message.get('order_id')}: {e}")
            raise

    async def handle_payment_succeeded(self, message: dict[str, Any]) -> None:
        """
        Handle payment.succeeded event.

        Ensures an order does not stay PENDING after Stripe confirms payment.
        We move PENDING -> CONFIRMED idempotently, but avoid overwriting CANCELLED.
        """
        try:
            event = PaymentSucceededEvent(**message)
            claimed = await self.idempotency_service.try_claim_event(event_id=event.event_id, event_type=event.event_type)
            if not claimed:
                self.logger.info(f"Skipping duplicate payment.succeeded event for order: {event.order_id}")
                return

            result = "payment_succeeded_noop"
            async for order_service in self._get_order_service():
                try:
                    current_order = await order_service.get_order_by_id(order_id=event.order_id)
                except OrderNotFoundError:
                    self.logger.warning(
                        f"Order {event.order_id} not found for payment.succeeded event — skipping"
                    )
                    result = "order_not_found"
                    break

                if current_order.status == OrderStatus.CANCELLED:
                    self.logger.info(
                        f"Order {event.order_id} already CANCELLED — skipping payment.succeeded transition"
                    )
                    result = "order_already_cancelled"
                    break

                if current_order.status == OrderStatus.PENDING:
                    _ = await order_service.update_order_status(
                        order_id=event.order_id,
                        order_status=OrderStatus.CONFIRMED,
                    )
                    self.logger.info(
                        f"Order {event.order_id} moved to {OrderStatus.CONFIRMED} on payment.succeeded"
                    )
                    confirmed_order = await order_service.get_order_with_details(order_id=event.order_id)
                    if confirmed_order:
                        event_data = self._build_order_confirmed_event_data(confirmed_order)
                        await order_event_publisher.publish_order_confirmed(event_data=event_data)
                        self.logger.info(f"Published OrderConfirmedEvent for order: {event.order_id}")
                    result = "payment_succeeded_confirmed"
                else:
                    result = f"no_transition_from_{current_order.status}"

            await self.idempotency_service.mark_event_as_processed(
                event_id=event.event_id,
                event_type=event.event_type,
                order_id=event.order_id,
                result=result,
            )

        except Exception as e:
            try:
                if message.get("event_id") and message.get("event_type"):
                    await self.idempotency_service.release_claim(
                        event_id=message["event_id"],
                        event_type=message["event_type"],
                    )
            except Exception:
                pass
            self.logger.error(f"Error handling payment.succeeded for order {message.get('order_id')}: {e}")
            raise

    async def handle_inventory_reserve_succeeded(self, message: dict[str, Any]):
        """
        Handle successful inventory reservation.

        Steps:
        1. Parse the event
        2. Guard against duplicate processing
        3. Fetch the current order — skip if not PENDING (e.g. already CANCELLED by user)
        4. Update order status to CONFIRMED in database
        5. Publish OrderConfirmedEvent for downstream services (e.g., notification / payments)
        """
        try:
            # Parse the event
            event = InventoryReserveSucceeded(**message)
            claimed = await self.idempotency_service.try_claim_event(event_id=event.event_id, event_type=event.event_type)
            if not claimed:
                self.logger.info(f"Skipping duplicate 'Inventory reservation succedded' event for order: {event.order_id}")
                return # skipping coa already processed
            self.logger.info(f"Processing 'Inventory reservation succedded' for order {event.order_id}")
            result = "inventory_succeeded_noop"
            # Get order service with database session
            async for order_service in self._get_order_service():
                # Guard: only confirm if the order is still PENDING.
                # The user may have cancelled the order while inventory reservation was in flight.
                try:
                    current_order = await order_service.get_order_by_id(order_id=event.order_id)
                except OrderNotFoundError:
                    self.logger.warning(f"Order: {event.order_id} not found — skipping inventory.reserve.succeeded")
                    result = "order_not_found"
                    break

                if current_order.status != OrderStatus.PENDING:
                    self.logger.warning(f"Order: {event.order_id} is '{current_order.status}' (expected PENDING) — skipping CONFIRMED transition to avoid overwriting a cancelled order")
                    result = f"no_transition_from_{current_order.status}"
                    break

                # Update order status to CONFIRMED
                _ = await order_service.update_order_status(
                    order_id=event.order_id,
                    order_status=OrderStatus.CONFIRMED
                )
                self.logger.info(f"Updated status to: {OrderStatus.CONFIRMED} for order id: {event.order_id}")
                result = "inventory_succeeded_confirmed"

            if result == "inventory_succeeded_confirmed":
                # Publish OrderConfirmedEvent for downstream services (notification, etc.)
                async for order_service in self._get_order_service():
                    confirmed_order = await order_service.get_order_with_details(order_id=event.order_id)
                    if confirmed_order:
                        event_data = self._build_order_confirmed_event_data(confirmed_order)
                        await order_event_publisher.publish_order_confirmed(event_data=event_data)
                        self.logger.info(f"Published OrderConfirmedEvent for order: {event.order_id}")
                        break

            # notification_service and payment_service consume order.confirmed
            # directly from the order.events.exchange — no further action required here.

            # marking an event as proccessed
            await self.idempotency_service.mark_event_as_processed(
                event_id=event.event_id,
                event_type=event.event_type,
                order_id=event.order_id,
                result=result
            )

            # TODO: notification service/payment services events -> ...

        except Exception as e:
            try:
                if message.get("event_id") and message.get("event_type"):
                    await self.idempotency_service.release_claim(
                        event_id=message["event_id"],
                        event_type=message["event_type"],
                    )
            except Exception:
                pass
            self.logger.error(f"Error handling inventory reserve succeeded for order {message.get('order_id')}: {str(e)}")
            raise

    async def handle_inventory_reserve_failed(self, message: dict[str, Any]):
        """
        Handle failed inventory reservation (SAGA Compensation).

        Steps:
        1. Parse the event
        2. Update order status to CANCELLED in database
        3. Publish OrderCancelledEvent for downstream services
        4. No need to release inventory since it was never reserved
        """
        try:
            # Parse the event
            event = InventoryReserveFailed(**message)
            claimed = await self.idempotency_service.try_claim_event(event_id=event.event_id, event_type=event.event_type)
            if not claimed:
                self.logger.info(f"Skipping duplicate 'Inventory reservation failed' event for order: {event.order_id}")
                return # skipping coa already processed
            self.logger.info(f"Inventory reservation failed for order {event.order_id}: {event.reasons}")
            result = "inventory_failed_cancelled"

            # Get order service with database session
            async for order_service in self._get_order_service():
                # Update order status to CANCELLED
                try:
                    _ = await order_service.update_order_status(
                        order_id=event.order_id,
                        order_status=OrderStatus.CANCELLED
                    )
                    self.logger.info(f"Updated status to {OrderStatus.CANCELLED} for order id: {event.order_id}")
                except OrderNotFoundError:
                    self.logger.warning(f"Order: {event.order_id} not found — skipping inventory.reserve.failed")
                    result = "order_not_found"
                    break

            # Publish OrderCancelledEvent for downstream services (notification, etc.)
            if result == "inventory_failed_cancelled":
                await order_event_publisher.publish_order_cancelled(
                    event_data={
                        "service": "order-service",
                        "event_type": "order.cancelled",
                        "order_id": str(event.order_id),
                        "user_id": str(event.user_id),
                        "user_email": event.user_email,
                        "reason": event.reasons,  # InventoryReserveFailed uses "reasons" (plural)
                    }
                )
                self.logger.info(f"Published OrderCancelledEvent for order {event.order_id}")

            # notification_service consumes order.cancelled to send cancellation emails.
            # payment_service consumes order.cancelled to issue refunds where applicable.

            await self.idempotency_service.mark_event_as_processed(
                event_id=event.event_id,
                event_type=event.event_type,
                order_id=event.order_id,
                result=result
            )
            # TODO: notification service/payment services events -> ...


        except Exception as e:
            try:
                if message.get("event_id") and message.get("event_type"):
                    await self.idempotency_service.release_claim(
                        event_id=message["event_id"],
                        event_type=message["event_type"],
                    )
            except Exception:
                pass
            self.logger.error(f"Error handling inventory reserve failed for order {message.get('order_id')}: {str(e)}")
            raise

    async def handle_payment_failed(self, message: dict[str, Any]):
        """
        Handle payment.failed event (SAGA compensation).

        When Stripe reports a payment failure the order must be cancelled so
        inventory is released and the customer is notified.

        Steps:
        1. Parse the event and guard against duplicates.
        2. Cancel the order via OrderService.cancel_order, which:
           a. Sets status to CANCELLED.
           b. Writes an OrderCancelledEvent outbox entry.
           c. Writes an InventoryReleaseRequested outbox entry when the order
              was already CONFIRMED (inventory had been reserved).
        3. Mark event as processed.

        OrderNotFoundError     → order was never persisted; skip silently.
        OrderNotCancellableError → order is already CANCELLED; idempotent skip.
        """
        try:
            event = PaymentFailedEvent(**message)

            claimed = await self.idempotency_service.try_claim_event(event_id=event.event_id, event_type=event.event_type)
            if not claimed:
                self.logger.info(f"Skipping duplicate payment.failed event for order: {event.order_id}")
                return

            self.logger.info(f"Processing payment.failed for order {event.order_id}: {event.reason}")
            result = "cancelled_due_to_payment_failure"

            async for order_service in self._get_order_service():
                try:
                    _ = await order_service.cancel_order(
                        order_id=event.order_id,
                        reason=f"Payment failed: {event.reason}",
                    )
                    self.logger.info(f"Order {event.order_id} cancelled due to payment failure")
                except OrderNotFoundError:
                    self.logger.warning(
                        f"Order {event.order_id} not found for payment.failed event — skipping"
                    )
                    result = "order_not_found"
                    break
                except OrderNotCancellableError:
                    self.logger.info(
                        f"Order {event.order_id} already CANCELLED — skipping payment.failed"
                    )
                    result = "order_already_cancelled"
                    break

            await self.idempotency_service.mark_event_as_processed(
                event_id=event.event_id,
                event_type=event.event_type,
                order_id=event.order_id,
                result=result,
            )

        except Exception as e:
            try:
                if message.get("event_id") and message.get("event_type"):
                    await self.idempotency_service.release_claim(
                        event_id=message["event_id"],
                        event_type=message["event_type"],
                    )
            except Exception:
                pass
            self.logger.error(f"Error handling payment.failed for order {message.get('order_id')}: {e}")
            raise

    async def handle_payment_cancelled(self, message: dict[str, Any]) -> None:
        """
        Handle payment.cancelled event (SAGA compensation).

        When Stripe cancels a PaymentIntent (expired, manually cancelled, etc.)
        the order must be cancelled so inventory is released and the customer
        is notified. Mirrors handle_payment_failed logic.

        OrderNotFoundError       → order was never persisted; skip silently.
        OrderNotCancellableError → order is already CANCELLED; idempotent skip.
        """
        try:
            event = PaymentCancelledEvent(**message)

            claimed = await self.idempotency_service.try_claim_event(event_id=event.event_id, event_type=event.event_type)
            if not claimed:
                self.logger.info(f"Skipping duplicate payment.cancelled event for order: {event.order_id}")
                return

            self.logger.info(f"Processing payment.cancelled for order {event.order_id}: {event.reason}")
            result = "cancelled_due_to_payment_cancellation"

            async for order_service in self._get_order_service():
                try:
                    _ = await order_service.cancel_order(
                        order_id=event.order_id,
                        reason=f"Payment cancelled: {event.reason}",
                    )
                    self.logger.info(f"Order {event.order_id} cancelled due to payment cancellation")
                except OrderNotFoundError:
                    self.logger.warning(
                        f"Order {event.order_id} not found for payment.cancelled event — skipping"
                    )
                    result = "order_not_found"
                    break
                except OrderNotCancellableError:
                    self.logger.info(
                        f"Order {event.order_id} already CANCELLED — skipping payment.cancelled"
                    )
                    result = "order_already_cancelled"
                    break

            await self.idempotency_service.mark_event_as_processed(
                event_id=event.event_id,
                event_type=event.event_type,
                order_id=event.order_id,
                result=result,
            )

        except Exception as e:
            try:
                if message.get("event_id") and message.get("event_type"):
                    await self.idempotency_service.release_claim(
                        event_id=message["event_id"],
                        event_type=message["event_type"],
                    )
            except Exception:
                pass
            self.logger.error(f"Error handling payment.cancelled for order {message.get('order_id')}: {e}")
            raise

    async def handle_shipping_event(self, message: dict[str, Any]) -> None:
        """Route shipping events to the appropriate handler."""
        event_type = message.get("event_type")
        match event_type:
            case ShippingEvents.SHIPMENT_CREATED:
                await self.handle_shipment_created(message)
            case ShippingEvents.SHIPMENT_SHIPPED:
                await self.handle_shipment_shipped(message)
            case ShippingEvents.SHIPMENT_DELIVERED:
                await self.handle_shipment_delivered(message)
            case ShippingEvents.SHIPMENT_CANCELLED:
                await self.handle_shipment_cancelled(message)
            case _:
                self.logger.warning(f"Unhandled shipping event type in order consumer: {event_type}")

    async def _update_delivery_status(self, message: dict[str, Any], status: OrderDeliveryStatus) -> None:
        """Helper to update order delivery status from shipping events."""
        event_type = message.get("event_type")
        event_id = message.get("event_id")

        try:
            claimed = await self.idempotency_service.try_claim_event(
                event_id=event_id,
                event_type=event_type,
            )
            if not claimed:
                self.logger.info(f"Skipping duplicate {event_type} event for order: {message.get('order_id')}")
                return

            result = f"delivery_status_{status}"
            async for order_service in self._get_order_service():
                try:
                    current_order = await order_service.get_order_by_id(order_id=message.get("order_id"))
                except OrderNotFoundError:
                    self.logger.warning(f"Order {message.get('order_id')} not found for {event_type} — skipping")
                    result = "order_not_found"
                    break

                if current_order.status == OrderStatus.CANCELLED:
                    self.logger.info(f"Order {message.get('order_id')} is CANCELLED — skipping {event_type}")
                    result = "order_cancelled"
                    break

                await order_service.update_delivery_status(
                    order_id=message.get("order_id"),
                    delivery_status=status,
                )
                self.logger.info(f"Updated delivery_status to {status} for order {message.get('order_id')}")

            await self.idempotency_service.mark_event_as_processed(
                event_id=event_id,
                event_type=event_type,
                order_id=message.get("order_id"),
                result=result,
            )

        except Exception as e:
            try:
                if event_id and event_type:
                    await self.idempotency_service.release_claim(
                        event_id=event_id,
                        event_type=event_type,
                    )
            except Exception:
                pass
            self.logger.error(f"Error handling {event_type} for order {message.get('order_id')}: {e}")
            raise

    async def handle_shipment_created(self, message: dict[str, Any]) -> None:
        """Order delivery status remains PENDING when shipment is created."""
        event = ShipmentCreatedEvent(**message)
        # No delivery status change; just log/idempotency so we don't reprocess.
        try:
            claimed = await self.idempotency_service.try_claim_event(
                event_id=event.event_id,
                event_type=event.event_type,
            )
            if not claimed:
                self.logger.info(f"Skipping duplicate shipment.created event for order: {event.order_id}")
                return

            await self.idempotency_service.mark_event_as_processed(
                event_id=event.event_id,
                event_type=event.event_type,
                order_id=event.order_id,
                result="delivery_status_pending",
            )
        except Exception as e:
            await self.idempotency_service.release_claim(
                event_id=event.event_id,
                event_type=event.event_type,
            )
            self.logger.error(f"Error handling shipment.created for order {event.order_id}: {e}")
            raise

    async def handle_shipment_shipped(self, message: dict[str, Any]) -> None:
        """Update order delivery_status to DISPATCHED."""
        await self._update_delivery_status(message, OrderDeliveryStatus.DISPATCHED)

    async def handle_shipment_delivered(self, message: dict[str, Any]) -> None:
        """Update order delivery_status to DELIVERED."""
        await self._update_delivery_status(message, OrderDeliveryStatus.DELIVERED)

    async def handle_shipment_cancelled(self, message: dict[str, Any]) -> None:
        """Update order delivery_status to CANCELLED."""
        await self._update_delivery_status(message, OrderDeliveryStatus.CANCELLED)


order_event_consumer = OrderEventConsumer(logger=logger)
