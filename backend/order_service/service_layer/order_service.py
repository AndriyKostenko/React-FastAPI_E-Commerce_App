from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from config import logger

from database_layer.order_fulfillment_repository import (
    CustomProductionJobRepository,
    OrderLineFulfillmentRepository,
)
from database_layer.order_repository import OrderRepository
from database_layer.order_saga_repository import OrderSagaRepository
from exceptions.order_exceptions import (
    DuplicatePaymentIntentError,
    OrderNotCancellableError,
    OrderNotFoundError,
    OrdersNotFoundError,
)
from models.order_fulfillment_models import CustomProductionJob
from models.order_models import Order
from models.order_saga_models import OrderSagaState
from schemas.order_schemas import (
    ConfirmedOrderAddress,
    ConfirmedOrderItem,
    CreateOrder,
    OrderAddressBase,
    OrderItemBase,
    OrderSchema,
    UpdateOrder,
)
from service_layer.order_address_service import OrderAddressService
from service_layer.order_fulfillment_status_service import OrderFulfillmentStatusService
from service_layer.order_item_service import OrderItemService
from service_layer.order_pricing_service import (
    CanonicalOrderQuote,
    OrderPricingService,
    OrderQuoteError,
)
from service_layer.outbox_event_service import OutboxEventService
from shared.contracts.events import (
    ArtworkReleasedEvent,
    ArtworkRetainedEvent,
    InventoryReleaseRequested,
    InventoryReserveRequested,
    OrderCancelledEvent,
    OrderConfirmedEvent,
    OrderCreatedEvent,
)
from shared.enums.event_enums import ArtworkEvents, InventoryEvents, OrderEvents
from shared.enums.services_enums import Services
from shared.enums.status_enums import (
    LineFulfillmentStatus,
    OrderDeliveryStatus,
    OrderStatus,
    ProductionJobStatus,
)


class OrderService:
    """Order aggregate and durable Saga state machine."""

    def __init__(
        self,
        repository: OrderRepository,
        order_item_service: OrderItemService,
        order_address_service: OrderAddressService,
        outbox_event_service: OutboxEventService,
        pricing_service: OrderPricingService | None = None,
        saga_repository: OrderSagaRepository | None = None,
        production_repository: CustomProductionJobRepository | None = None,
        fulfillment_status_service: OrderFulfillmentStatusService | None = None,
    ):
        self.repository = repository
        self.outbox_event_service = outbox_event_service
        self.order_item_service = order_item_service
        self.order_address_service = order_address_service
        self.pricing_service = pricing_service
        self.saga_repository = saga_repository or OrderSagaRepository(repository.session)
        self.production_repository = production_repository or CustomProductionJobRepository(
            repository.session
        )
        self.fulfillment_status_service = (
            fulfillment_status_service
            or OrderFulfillmentStatusService(
                order_repository=repository,
                fulfillment_repository=OrderLineFulfillmentRepository(repository.session),
            )
        )

    async def create_order(self, order_data: CreateOrder) -> OrderSchema:
        """Create a server-priced pending order and start inventory reservation."""
        if self.pricing_service is None:
            raise RuntimeError("OrderPricingService is required to create orders")

        quote = await self.pricing_service.build_quote(order_data)
        self._validate_fulfillment_address(order_data, quote)
        inventory_required = any(
            item.fulfillment_type != "custom" for item in quote.items
        )

        try:
            async with self.repository.session.begin_nested():
                address = await self.order_address_service.create_order_address(order_data)
                fields = {
                    "user_id": order_data.user_id,
                    "user_email": order_data.user_email,
                    "amount": float(quote.total_amount),
                    "currency": quote.currency.lower(),
                    "status": OrderStatus.PENDING,
                    "delivery_status": OrderDeliveryStatus.PENDING,
                    "payment_intent_id": order_data.payment_intent_id,
                    "address_id": address.id,
                }
                if order_data.id:
                    fields["id"] = order_data.id
                order = await self.repository.create(Order(**fields))
                items = await self.order_item_service.create_order_items(order.id, quote)
                await self.saga_repository.create(
                    OrderSagaState(
                        order_id=order.id,
                        inventory_status="pending" if inventory_required else "not_required",
                        payment_status="pending",
                        fulfillment_status="pending",
                    )
                )

                await self.outbox_event_service.add_outbox_event(
                    event_type=OrderEvents.ORDER_CREATED,
                    payload=OrderCreatedEvent(
                        service=Services.ORDER_SERVICE,
                        event_type=OrderEvents.ORDER_CREATED,
                        order_id=order.id,
                        user_id=order.user_id,
                        user_email=order.user_email,
                        items=items,
                        total_amount=order.amount,
                    ),
                )

                inventory_items = [
                    item for item in items if item.fulfillment_type != "custom"
                ]
                if inventory_items:
                    await self.outbox_event_service.add_outbox_event(
                        event_type=InventoryEvents.INVENTORY_RESERVE_REQUESTED,
                        payload=InventoryReserveRequested(
                            service=Services.ORDER_SERVICE,
                            event_type=InventoryEvents.INVENTORY_RESERVE_REQUESTED,
                            order_id=order.id,
                            user_id=order.user_id,
                            user_email=order.user_email,
                            items=inventory_items,
                        ),
                    )
        except IntegrityError as exc:
            if order_data.payment_intent_id:
                raise DuplicatePaymentIntentError(order_data.payment_intent_id) from exc
            raise

        return OrderSchema.model_validate(order)

    @staticmethod
    def _validate_fulfillment_address(
        order_data: CreateOrder,
        quote: CanonicalOrderQuote,
    ) -> None:
        if not any(line.fulfillment_type == "cj" for line in quote.items):
            return
        address = order_data.address
        required = {
            "country": address.country,
            "country_code": address.country_code,
            "name": address.name,
            "phone": address.phone,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise OrderQuoteError(
                f"CJ fulfillment requires address fields: {', '.join(missing)}"
            )

    async def record_inventory_succeeded(self, order_id: UUID) -> OrderSchema:
        """Record reservation and confirm only when payment also succeeded."""
        async with self.repository.session.begin_nested():
            saga = await self._get_saga_for_update(order_id)
            order = await self._get_order(order_id)
            if order.status == OrderStatus.CANCELLED:
                if saga.inventory_status not in {"released", "release_requested"}:
                    saga.inventory_status = "release_requested"
                    await self._add_inventory_release(order, "Order cancelled during reservation")
                return OrderSchema.model_validate(order)
            saga.inventory_status = "reserved"
            saga.version += 1
            await self.saga_repository.update(saga)
            await self._confirm_if_ready(order, saga)
        return OrderSchema.model_validate(order)

    async def record_inventory_failed(self, order_id: UUID, reason: str) -> OrderSchema:
        async with self.repository.session.begin_nested():
            saga = await self._get_saga_for_update(order_id)
            order = await self._get_order(order_id)
            saga.inventory_status = "failed"
            await self.saga_repository.update(saga)
            if order.status != OrderStatus.CANCELLED:
                await self._cancel_locked(order, saga, reason, release_inventory=False)
        return OrderSchema.model_validate(order)

    async def record_payment_succeeded(
        self,
        order_id: UUID,
        *,
        user_id: UUID,
        amount_cents: int,
        currency: str,
        payment_intent_id: str,
    ) -> OrderSchema:
        """Record payment only after validating it against the canonical quote."""
        async with self.repository.session.begin_nested():
            saga = await self._get_saga_for_update(order_id)
            order = await self._get_order(order_id)
            if order.status == OrderStatus.CANCELLED:
                return OrderSchema.model_validate(order)
            expected_cents = int(
                (Decimal(str(order.amount)) * 100).quantize(Decimal("1"))
            )
            identity_mismatch = (
                order.user_id != user_id
                or (
                    order.payment_intent_id is not None
                    and order.payment_intent_id != payment_intent_id
                )
            )
            if (
                identity_mismatch
                or amount_cents != expected_cents
                or currency.lower() != order.currency.lower()
            ):
                await self._cancel_locked(
                    order,
                    saga,
                    "Payment identity, amount, or currency does not match the canonical order",
                )
                return OrderSchema.model_validate(order)
            order.payment_intent_id = payment_intent_id
            saga.payment_status = "succeeded"
            saga.version += 1
            await self.repository.update(order)
            await self.saga_repository.update(saga)
            await self._confirm_if_ready(order, saga)
        return OrderSchema.model_validate(order)

    async def record_payment_failed(self, order_id: UUID, reason: str) -> OrderSchema:
        async with self.repository.session.begin_nested():
            saga = await self._get_saga_for_update(order_id)
            order = await self._get_order(order_id)
            saga.payment_status = "failed"
            await self.saga_repository.update(saga)
            if order.status != OrderStatus.CANCELLED:
                await self._cancel_locked(order, saga, reason)
        return OrderSchema.model_validate(order)

    async def record_fulfillment_failed(
        self, order_id: UUID, reason: str
    ) -> OrderSchema:
        """Compensate a confirmed order after a definitive fulfillment failure."""
        async with self.repository.session.begin_nested():
            saga = await self._get_saga_for_update(order_id)
            order = await self._get_order(order_id)
            saga.fulfillment_status = "failed"
            await self.saga_repository.update(saga)
            if order.status != OrderStatus.CANCELLED:
                await self._cancel_locked(order, saga, reason)
        return OrderSchema.model_validate(order)

    async def _confirm_if_ready(self, order: Order, saga: OrderSagaState) -> None:
        inventory_ready = saga.inventory_status in {"reserved", "not_required"}
        if (
            order.status != OrderStatus.PENDING
            or saga.payment_status != "succeeded"
            or not inventory_ready
        ):
            return

        order.status = OrderStatus.CONFIRMED
        saga.fulfillment_status = "ready"
        saga.version += 1
        await self.repository.update(order)
        await self.saga_repository.update(saga)

        detailed = await self.get_order_with_details(order.id)
        if detailed is None:
            raise OrderNotFoundError(order.id)
        await self._queue_custom_production(detailed)
        await self._retain_ordered_artwork(detailed)
        await self.outbox_event_service.add_outbox_event(
            event_type=OrderEvents.ORDER_CONFIRMED,
            payload=self._build_order_confirmed_event(detailed),
        )

    async def _queue_custom_production(self, order: Order) -> None:
        for item in order.items:
            fulfillment = item.fulfillment
            if not fulfillment or fulfillment.fulfillment_type != "custom":
                continue
            existing = await self.production_repository.get_by_field(
                "order_item_id", item.id
            )
            if existing:
                continue
            await self.production_repository.create(
                CustomProductionJob(
                    order_id=order.id,
                    order_item_id=item.id,
                    specifications=fulfillment.customization or {},
                    quantity=item.quantity,
                    status=ProductionJobStatus.QUEUED,
                )
            )
            fulfillment.status = LineFulfillmentStatus.QUEUED

    @staticmethod
    def _ordered_artwork_keys(order: Order) -> list[str]:
        """Object keys of every print file this order's custom lines need."""
        keys: list[str] = []
        for item in order.items or []:
            fulfillment = item.fulfillment
            if not fulfillment or fulfillment.fulfillment_type != "custom":
                continue
            asset = (fulfillment.customization or {}).get("design_asset") or {}
            key = asset.get("key")
            if key:
                keys.append(key)
        return keys

    async def _retain_ordered_artwork(self, order: Order) -> None:
        """Tell product_service its stored print files are now spoken for.

        product_service owns the artwork object while this service owns the
        reference, so without this marker a cleanup job sweeping unreferenced
        generation drafts cannot tell a paid order's print file from an
        abandoned preview and could delete artwork still waiting to be printed.
        """
        keys = self._ordered_artwork_keys(order)
        if not keys:
            return
        await self.outbox_event_service.add_outbox_event(
            event_type=ArtworkEvents.ARTWORK_RETAINED,
            payload=ArtworkRetainedEvent(
                service=Services.ORDER_SERVICE,
                event_type=ArtworkEvents.ARTWORK_RETAINED,
                order_id=order.id,
                artwork_keys=keys,
            ),
        )

    def _build_order_confirmed_event(self, order: Order) -> OrderConfirmedEvent:
        items = []
        for item in order.items or []:
            fulfillment = item.fulfillment
            if fulfillment is None:
                raise RuntimeError(f"Order item {item.id} has no fulfillment snapshot")
            items.append(
                ConfirmedOrderItem(
                    product_id=item.product_id,
                    variant_id=item.variant_id,
                    quantity=item.quantity,
                    price=item.price,
                    fulfillment_type=fulfillment.fulfillment_type,
                    product_name=fulfillment.product_name,
                    customization=fulfillment.customization,
                    variant_snapshot=fulfillment.variant_snapshot,
                )
            )
        address = order.address
        return OrderConfirmedEvent(
            service=Services.ORDER_SERVICE,
            event_type=OrderEvents.ORDER_CONFIRMED,
            order_id=order.id,
            user_id=order.user_id,
            user_email=order.user_email,
            items=items,
            address=ConfirmedOrderAddress(
                street=address.street or "",
                city=address.city or "",
                province=address.province or "",
                postal_code=address.postal_code or "",
                country=address.country,
                country_code=address.country_code,
                name=address.name,
                phone=address.phone,
            ),
        )

    async def cancel_order(self, order_id: UUID, reason: str) -> OrderSchema:
        """Cancel an order that has not yet cost anything irreversible.

        The guard is per line rather than order-level. A custom T-shirt is
        printed at home and never reaches ``delivery_status=delivered`` on its
        own, so an order-level delivered check never binds for it and printed,
        posted goods stayed cancellable-and-refundable. Asking the lines
        instead covers every fulfillment channel with one rule.
        """
        async with self.repository.session.begin_nested():
            saga = await self._get_saga_for_update(order_id)
            order = await self._get_order(order_id)
            if order.status == OrderStatus.CANCELLED:
                raise OrderNotCancellableError(order_id, order.status)
            if order.delivery_status == OrderDeliveryStatus.DELIVERED:
                raise OrderNotCancellableError(order_id, order.delivery_status)

            blocking = await self._blocking_line_status(order_id)
            if blocking is not None:
                raise OrderNotCancellableError(order_id, blocking)

            await self._cancel_locked(order, saga, reason)
        return OrderSchema.model_validate(order)

    async def _blocking_line_status(self, order_id: UUID) -> str | None:
        """The status of the first line too far along to cancel, if any."""
        lines = await self.fulfillment_status_service.get_lines(order_id)
        for line in lines:
            if line.blocks_cancellation:
                return line.status
        return None

    async def _cancel_locked(
        self,
        order: Order,
        saga: OrderSagaState,
        reason: str,
        *,
        release_inventory: bool = True,
    ) -> None:
        """Compensate an order, holding the refund back on work already done.

        The in-house queue is settled *before* the cancellation event is
        written, because whether any garment had already been printed or
        posted decides whether the refund may run automatically at all.
        """
        detailed = await self.get_order_with_details(order.id) or order
        needs_reconciliation = await self._cancel_production_jobs(detailed, reason)
        await self._release_ordered_artwork(detailed, reason)

        order.status = OrderStatus.CANCELLED
        order.delivery_status = OrderDeliveryStatus.CANCELLED
        saga.fulfillment_status = "cancelled"
        saga.cancellation_reason = reason
        saga.version += 1
        await self.repository.update(order)
        await self.saga_repository.update(saga)
        await self.fulfillment_status_service.mark_lines(
            order, LineFulfillmentStatus.CANCELLED
        )

        if needs_reconciliation:
            self._logger_warn_reconciliation(order.id, reason)

        await self.outbox_event_service.add_outbox_event(
            event_type=OrderEvents.ORDER_CANCELLED,
            payload=OrderCancelledEvent(
                service=Services.ORDER_SERVICE,
                event_type=OrderEvents.ORDER_CANCELLED,
                order_id=order.id,
                user_id=order.user_id,
                user_email=order.user_email,
                reason=reason,
                reconciliation_required=needs_reconciliation,
            ),
        )
        if release_inventory and saga.inventory_status == "reserved":
            saga.inventory_status = "release_requested"
            await self._add_inventory_release(order, reason)

    @staticmethod
    def _logger_warn_reconciliation(order_id: UUID, reason: str) -> None:
        """Make a held-back refund loud enough for an operator to notice."""
        logger.critical(
            "RECONCILIATION REQUIRED for order %s: cancelled (%s) after the "
            "in-house garment was already printed or posted. Automatic refund "
            "is blocked pending a return decision.",
            order_id,
            reason,
        )

    async def _cancel_production_jobs(self, order: Order, reason: str) -> bool:
        """Take this order's in-house jobs off the queue, flagging spent work.

        A job that was already printed or posted has consumed a blank garment
        and ink, or put real goods in the post. Cancelling it is recorded but
        marked ``reconciliation_required`` so a human decides on return and
        refund, exactly as a CJ order already shipped is handled — refunding
        it automatically pays back money against stock that is gone.
        """
        needs_reconciliation = False
        jobs = await self.production_repository.get_many_by_field("order_id", order.id)
        for job in jobs or []:
            status = ProductionJobStatus(job.status)
            if status in ProductionJobStatus.terminal():
                continue
            if status in ProductionJobStatus.needs_reconciliation_on_cancel():
                job.reconciliation_required = True
                needs_reconciliation = True
            job.status = ProductionJobStatus.CANCELLED
            job.cancelled_at = datetime.now(UTC)
            job.cancellation_reason = reason[:500]
            await self.production_repository.update(job)
        return needs_reconciliation

    async def _release_ordered_artwork(self, order: Order, reason: str) -> None:
        """Drop the retention holds of an order that can no longer be printed."""
        keys = self._ordered_artwork_keys(order)
        if not keys:
            return
        await self.outbox_event_service.add_outbox_event(
            event_type=ArtworkEvents.ARTWORK_RELEASED,
            payload=ArtworkReleasedEvent(
                service=Services.ORDER_SERVICE,
                event_type=ArtworkEvents.ARTWORK_RELEASED,
                order_id=order.id,
                artwork_keys=keys,
                reason=reason,
            ),
        )

    async def _add_inventory_release(self, order: Order, reason: str) -> None:
        items = [
            item
            for item in await self.order_item_service.get_items_by_order_id(order.id)
            if item.fulfillment_type != "custom"
        ]
        if not items:
            return
        await self.outbox_event_service.add_outbox_event(
            event_type=InventoryEvents.INVENTORY_RELEASE_REQUESTED,
            payload=InventoryReleaseRequested(
                service=Services.ORDER_SERVICE,
                event_type=InventoryEvents.INVENTORY_RELEASE_REQUESTED,
                order_id=order.id,
                user_id=order.user_id,
                user_email=order.user_email,
                items=items,
                reason=reason,
            ),
        )

    async def _get_order(self, order_id: UUID) -> Order:
        order = await self.repository.get_by_id(order_id)
        if not order:
            raise OrderNotFoundError(order_id)
        return order

    async def _get_saga_for_update(self, order_id: UUID) -> OrderSagaState:
        saga = await self.saga_repository.get_for_update(order_id)
        if not saga:
            raise OrderNotFoundError(order_id)
        return saga

    async def get_order_by_id(self, order_id: UUID) -> OrderSchema:
        return OrderSchema.model_validate(await self._get_order(order_id))

    async def get_order_with_details(self, order_id: UUID) -> Order | None:
        return await self.repository.get_with_fulfillment(order_id)

    async def update_order_status(self, order_id: UUID, order_status: str) -> OrderSchema:
        updated = await self.repository.update_by_id(order_id, {"status": order_status})
        if not updated:
            raise OrderNotFoundError(order_id)
        return OrderSchema.model_validate(updated)

    async def record_line_fulfillment(
        self,
        order_id: UUID,
        status: LineFulfillmentStatus,
        *,
        fulfillment_types: set[str],
    ) -> OrderSchema:
        """Advance one fulfillment channel's lines and re-derive the order status.

        CJ and the local warehouse both report progress for a whole order, but
        an order can hold lines from several channels at once. Scoping the
        update to the reporting channel's lines is what stops a dropshipped
        parcel from marking an unprinted custom T-shirt as dispatched.
        """
        async with self.repository.session.begin_nested():
            order = await self._get_order(order_id)
            await self.fulfillment_status_service.mark_lines(
                order, status, fulfillment_types=fulfillment_types
            )
        return OrderSchema.model_validate(order)

    async def update_delivery_status(self, order_id: UUID, delivery_status: str) -> OrderSchema:
        updated = await self.repository.update_by_id(
            order_id, {"delivery_status": delivery_status}
        )
        if not updated:
            raise OrderNotFoundError(order_id)
        return OrderSchema.model_validate(updated)

    async def create_order_item(
        self, order_id: UUID, quote: CanonicalOrderQuote
    ) -> list[OrderItemBase]:
        return await self.order_item_service.create_order_items(order_id, quote)

    async def create_order_address(self, order_data: CreateOrder) -> OrderAddressBase:
        return await self.order_address_service.create_order_address(order_data)

    async def get_orders(self) -> list[OrderSchema]:
        orders = await self.repository.get_all()
        if not orders:
            raise OrdersNotFoundError()
        return [OrderSchema.model_validate(order) for order in orders]

    async def get_orders_by_user_id(self, user_id: UUID) -> list[OrderSchema]:
        orders = await self.repository.get_many_by_field("user_id", user_id)
        if not orders:
            raise OrdersNotFoundError()
        return [OrderSchema.model_validate(order) for order in orders]

    async def update_order(self, order_id: UUID, order_data: UpdateOrder) -> OrderSchema:
        """Administrative metadata update; Saga status cannot be forced here."""
        fields = order_data.model_dump(exclude_unset=True, exclude={"status"})
        if not fields:
            return await self.get_order_by_id(order_id)
        updated = await self.repository.update_by_id(order_id, fields)
        if not updated:
            raise OrderNotFoundError(order_id)
        return OrderSchema.model_validate(updated)

    async def delete_order_by_id(self, order_id: UUID) -> None:
        deleted = await self.repository.delete_by_id(order_id)
        if not deleted:
            raise OrderNotFoundError(order_id)
