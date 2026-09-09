from logging import Logger
from typing import Any

from database_layer.order_address_repository import OrderAddressRepository
from database_layer.order_fulfillment_repository import OrderLineFulfillmentRepository
from database_layer.order_item_repository import OrderItemRepository
from database_layer.order_repository import OrderRepository
from shared.database_layer.outbox_repository import OutboxRepository
from events_publisher.order_event_publisher import OrderEventPublisher
from service_layer.order_address_service import OrderAddressService
from service_layer.order_fulfillment_status_service import OrderFulfillmentStatusService
from service_layer.order_item_service import OrderItemService
from schemas.order_schemas import UpdateOrder
from shared.contracts.events import (
    CJOrderCreatedEvent,
    CJOrderDeliveredEvent,
    CJOrderFailedEvent,
    CJOrderShippedEvent,
    InventoryReserveFailed,
    InventoryReserveSucceeded,
    PaymentSucceededEvent,
    PaymentFailedEvent,
    PaymentCancelledEvent,
    ShipmentCreatedEvent,
    ShipmentShippedEvent,
    ShipmentDeliveredEvent,
    ShipmentCancelledEvent,
)
from service_layer.order_service import OrderService
from shared.enums.status_enums import LineFulfillmentStatus, OrderStatus
from service_layer.outbox_event_service import OutboxEventService
from models.outbox_models import OutboxEvent
from shared.idempotency.idempotency_service import IdempotencyEventService
from shared.managers.database_session_manager import DatabaseSessionManager
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
    def __init__(
        self,
        logger: Logger,
        database: DatabaseSessionManager,
        idempotency_service: IdempotencyEventService,
        event_publisher: OrderEventPublisher,
    ) -> None:
        self.logger: Logger = logger
        self.database = database
        self.idempotency_service = idempotency_service
        self.event_publisher = event_publisher

    async def _get_order_service(self):
        """
        Creating an OrderService instance with a fresh database session.
        This is similar to FastAPI's dependency injection but for FastStream consumers.
        """
        async with self.database.transaction() as session:
            order_item_service = OrderItemService(
                repository=OrderItemRepository(session=session)
            )
            order_address_service = OrderAddressService(
                repository=OrderAddressRepository(session=session)
            )
            outbox_event_service = OutboxEventService(
                repository=OutboxRepository(session=session, model=OutboxEvent)
            )
            order_repository = OrderRepository(session=session)
            order_service = OrderService(
                repository=order_repository,
                order_item_service=order_item_service,
                order_address_service=order_address_service,
                outbox_event_service=outbox_event_service,
                fulfillment_status_service=OrderFulfillmentStatusService(
                    order_repository=order_repository,
                    fulfillment_repository=OrderLineFulfillmentRepository(session=session),
                ),
            )
            yield order_service

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

    async def handle_cj_order_event(self, message: dict[str, Any]) -> None:
        """Route every CJ fulfillment event to its handler."""
        event_type = message.get("event_type")
        match event_type:
            case OrderEvents.CJ_ORDER_CREATED:
                await self.handle_cj_order_created(message)
            case OrderEvents.CJ_ORDER_SHIPPED:
                await self.handle_cj_order_shipped(message)
            case OrderEvents.CJ_ORDER_DELIVERED:
                await self.handle_cj_order_delivered(message)
            case OrderEvents.CJ_ORDER_FAILED:
                await self.handle_cj_order_failed(message)
            case _:
                self.logger.warning("Unhandled CJ event: %s", event_type)

    async def handle_cj_order_shipped(self, message: dict[str, Any]) -> None:
        """CJ handed the parcel to the carrier: the order is on its way."""
        event = CJOrderShippedEvent(**message)
        self.logger.info(
            f"CJ order {event.cj_order_number} shipped for order {event.order_id} "
            f"with tracking {event.tracking_number}"
        )
        await self._record_line_fulfillment(
            message, LineFulfillmentStatus.SHIPPED, {"cj"}
        )

    async def handle_cj_order_delivered(self, message: dict[str, Any]) -> None:
        """CJ's carrier reported the parcel as delivered."""
        event = CJOrderDeliveredEvent(**message)
        self.logger.info(
            f"CJ order {event.cj_order_number} delivered for order {event.order_id}"
        )
        await self._record_line_fulfillment(
            message, LineFulfillmentStatus.DELIVERED, {"cj"}
        )

    async def handle_cj_order_failed(self, message: dict[str, Any]) -> None:
        """Compensate the saga after a definitive CJ fulfillment failure.

        This covers both a rejected submission and an order CJ cancelled after
        accepting it; cancelling the order is what triggers the Stripe refund.
        """
        event = CJOrderFailedEvent(**message)
        if not await self.idempotency_service.try_claim_event(
            event.event_id, event.event_type
        ):
            return
        try:
            result = "cj_failure_compensated"
            async for order_service in self._get_order_service():
                try:
                    await order_service.record_fulfillment_failed(
                        event.order_id, f"CJ fulfillment failed: {event.reason}"
                    )
                except OrderNotFoundError:
                    result = "order_not_found"
            await self.idempotency_service.mark_event_as_processed(
                event.event_id, event.event_type, event.order_id, result
            )
        except Exception:
            await self.idempotency_service.release_claim(
                event.event_id, event.event_type
            )
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

            result = "payment_succeeded_recorded"
            async for order_service in self._get_order_service():
                try:
                    updated = await order_service.record_payment_succeeded(
                        order_id=event.order_id,
                        user_id=event.user_id,
                        amount_cents=int(event.amount),
                        currency=event.currency,
                        payment_intent_id=event.payment_intent_id,
                    )
                except OrderNotFoundError:
                    self.logger.warning(
                        f"Order {event.order_id} not found for payment.succeeded event — skipping"
                    )
                    result = "order_not_found"
                    break

                result = f"payment_succeeded_{updated.status}"

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
            result = "inventory_succeeded_recorded"
            # Get order service with database session
            async for order_service in self._get_order_service():
                # Guard: only confirm if the order is still PENDING.
                # The user may have cancelled the order while inventory reservation was in flight.
                try:
                    updated = await order_service.record_inventory_succeeded(
                        order_id=event.order_id
                    )
                except OrderNotFoundError:
                    self.logger.warning(f"Order: {event.order_id} not found — skipping inventory.reserve.succeeded")
                    result = "order_not_found"
                    break

                result = f"inventory_succeeded_{updated.status}"

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
                    _ = await order_service.record_inventory_failed(
                        order_id=event.order_id,
                        reason=event.reasons,
                    )
                    self.logger.info(f"Updated status to {OrderStatus.CANCELLED} for order id: {event.order_id}")
                except OrderNotFoundError:
                    self.logger.warning(f"Order: {event.order_id} not found — skipping inventory.reserve.failed")
                    result = "order_not_found"
                    break

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
                    _ = await order_service.record_payment_failed(
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
                    _ = await order_service.record_payment_failed(
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

    async def _record_line_fulfillment(
        self,
        message: dict[str, Any],
        status: LineFulfillmentStatus,
        fulfillment_types: set[str],
    ) -> None:
        """Record progress reported by one fulfillment channel.

        Both CJ and the local warehouse report per order, not per line, but an
        order can hold lines from several channels at once. Scoping the update
        to the reporting channel's lines and re-deriving the order-level status
        from all of them is what stops a dropshipped parcel from marking an
        unprinted custom T-shirt as dispatched.
        """
        event_type = message.get("event_type")
        event_id = message.get("event_id")
        order_id = message.get("order_id")

        try:
            claimed = await self.idempotency_service.try_claim_event(
                event_id=event_id,
                event_type=event_type,
            )
            if not claimed:
                self.logger.info(f"Skipping duplicate {event_type} event for order: {order_id}")
                return

            result = f"line_fulfillment_{status}"
            async for order_service in self._get_order_service():
                try:
                    current_order = await order_service.get_order_by_id(order_id=order_id)
                except OrderNotFoundError:
                    self.logger.warning(f"Order {order_id} not found for {event_type} — skipping")
                    result = "order_not_found"
                    break

                if current_order.status == OrderStatus.CANCELLED:
                    self.logger.info(f"Order {order_id} is CANCELLED — skipping {event_type}")
                    result = "order_cancelled"
                    break

                updated = await order_service.record_line_fulfillment(
                    order_id=order_id,
                    status=status,
                    fulfillment_types=fulfillment_types,
                )
                self.logger.info(
                    f"Recorded {status} on {sorted(fulfillment_types)} lines of order "
                    f"{order_id}; delivery_status is now {updated.delivery_status}"
                )
                result = f"line_fulfillment_{status}_{updated.delivery_status}"

            await self.idempotency_service.mark_event_as_processed(
                event_id=event_id,
                event_type=event_type,
                order_id=order_id,
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
            self.logger.error(f"Error handling {event_type} for order {order_id}: {e}")
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
        """Mark the locally shipped catalog lines as dispatched.

        shipping_service creates a local shipment only for ``catalog`` lines —
        CJ owns delivery for its own lines and the in-house queue posts custom
        ones — so its events speak for the catalog lines alone.
        """
        await self._record_line_fulfillment(
            message, LineFulfillmentStatus.SHIPPED, {"catalog"}
        )

    async def handle_shipment_delivered(self, message: dict[str, Any]) -> None:
        """Mark the locally shipped catalog lines as delivered."""
        await self._record_line_fulfillment(
            message, LineFulfillmentStatus.DELIVERED, {"catalog"}
        )

    async def handle_shipment_cancelled(self, message: dict[str, Any]) -> None:
        """Mark the locally shipped catalog lines as cancelled."""
        await self._record_line_fulfillment(
            message, LineFulfillmentStatus.CANCELLED, {"catalog"}
        )
