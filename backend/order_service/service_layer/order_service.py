from uuid import UUID

from sqlalchemy.exc import IntegrityError

from service_layer.order_address_service import OrderAddressService
from service_layer.order_item_service import OrderItemService
from database_layer.order_repository import OrderRepository
from models.order_models import Order
from service_layer.outbox_event_service import OutboxEventService
from shared.schemas.order_schemas import CreateOrder, OrderItemBase, OrderSchema, OrderAddressBase, UpdateOrder
from exceptions.order_exceptions import OrderNotFoundError, OrdersNotFoundError, DuplicatePaymentIntentError, OrderNotCancellableError
from shared.schemas.event_schemas import (
    OrderCreatedEvent,
    InventoryReserveRequested,
    OrderCancelledEvent,
    InventoryReleaseRequested,
    OrderConfirmedEvent,
)
from shared.enums.event_enums import InventoryEvents, OrderEvents
from shared.enums.status_enums import OrderStatus, OrderDeliveryStatus
from shared.enums.services_enums import Services

class OrderService:
    """Service layer for order management operations, business logic, data validation."""
    def __init__(self, repository: OrderRepository, order_item_service: OrderItemService, order_address_service: OrderAddressService, outbox_event_service: OutboxEventService):
        self.repository: OrderRepository = repository
        self.outbox_event_service: OutboxEventService = outbox_event_service
        self.order_item_service: OrderItemService = order_item_service
        self.order_address_service:OrderAddressService = order_address_service

    async def create_order(self, order_data: CreateOrder) -> OrderSchema:
        """
        Creating new order with outbox events.
        The order status is "pending" untill the inventory is confirmed
        """
        try:
            async with self.repository.session.begin_nested():
                # 1. creating an order address
                new_db_order_address: OrderAddressBase = await self.order_address_service.create_order_address(order_data)
                # 2. creating order
                order_fields = {
                    "user_id": order_data.user_id,
                    "user_email": order_data.user_email,
                    "amount": order_data.amount,
                    "currency": order_data.currency,
                    "status": OrderStatus.PENDING,
                    "delivery_status": OrderDeliveryStatus.PENDING,
                    "payment_intent_id": order_data.payment_intent_id,
                    "address_id": new_db_order_address.id,
                }
                if order_data.id:
                    order_fields["id"] = order_data.id

                new_db_order: Order = await self.repository.create(
                    Order(**order_fields)
                )
                # 3. creating order items
                new_db_order_items: list[OrderItemBase]  = await self.order_item_service.create_order_items(new_db_order.id, order_data)

                # 4. creating outbox event "order.created"
                await self.outbox_event_service.add_outbox_event(
                    event_type=OrderEvents.ORDER_CREATED,
                    payload=OrderCreatedEvent(
                        service=Services.ORDER_SERVICE,
                        event_type=OrderEvents.ORDER_CREATED,
                        order_id=new_db_order.id,
                        user_id=new_db_order.user_id,
                        user_email=new_db_order.user_email,
                        items=new_db_order_items,
                        total_amount=new_db_order.amount
                    )
                )

                # 5. creating outbox event "inventory.reserve.requested"
                await self.outbox_event_service.add_outbox_event(
                    event_type=InventoryEvents.INVENTORY_RESERVE_REQUESTED,
                    payload=InventoryReserveRequested(
                        service=Services.ORDER_SERVICE,
                        event_type=InventoryEvents.INVENTORY_RESERVE_REQUESTED,
                        order_id=new_db_order.id,
                        user_id=new_db_order.user_id,
                        user_email=new_db_order.user_email,
                        items=new_db_order_items
                    )
                )
        except IntegrityError:
            raise DuplicatePaymentIntentError(payment_intent_id=order_data.payment_intent_id)

        return OrderSchema.model_validate(new_db_order)

    async def cancel_order(self, order_id: UUID, reason: str) -> OrderSchema:
        """
        Cancel an order initiated by the user or admin.

        Only PENDING or CONFIRMED orders can be cancelled. If the order was
        already CONFIRMED (inventory reserved), an InventoryReleaseRequested
        outbox event is emitted so the product service can roll back stock.
        """
        db_order = await self.repository.get_by_id(order_id)
        if not db_order:
            raise OrderNotFoundError(order_id)

        if db_order.status == OrderStatus.CANCELLED:
            raise OrderNotCancellableError(order_id, db_order.status)

        was_confirmed = db_order.status == OrderStatus.CONFIRMED

        async with self.repository.session.begin_nested():
            updated_order = await self.repository.update_by_id(
                order_id, data={"status": OrderStatus.CANCELLED}
            )
            # Notify downstream services that the order is cancelled
            await self.outbox_event_service.add_outbox_event(
                event_type=OrderEvents.ORDER_CANCELLED,
                payload=OrderCancelledEvent(
                    service=Services.ORDER_SERVICE,
                    event_type=OrderEvents.ORDER_CANCELLED,
                    order_id=db_order.id,
                    user_id=db_order.user_id,
                    user_email=db_order.user_email,
                    reason=reason,
                ),
            )
            # If inventory was already reserved, request its release
            if was_confirmed:
                order_items = await self.order_item_service.get_items_by_order_id(order_id)
                await self.outbox_event_service.add_outbox_event(
                    event_type=InventoryEvents.INVENTORY_RELEASE_REQUESTED,
                    payload=InventoryReleaseRequested(
                        service=Services.PRODUCT_SERVICE,
                        event_type=InventoryEvents.INVENTORY_RELEASE_REQUESTED,
                        order_id=db_order.id,
                        user_id=db_order.user_id,
                        user_email=db_order.user_email,
                        items=order_items,
                        reason=reason,
                    ),
                )

        return OrderSchema.model_validate(updated_order)

    async def get_order_by_id(self, order_id: UUID) -> OrderSchema:
        db_order = await self.repository.get_by_id(order_id)
        if not db_order:
            raise OrderNotFoundError(order_id)
        return OrderSchema.model_validate(db_order)

    async def update_order_status(self, order_id: UUID, order_status: str) -> OrderSchema:
        updated_db_order = await self.repository.update_by_id(order_id, data={"status": order_status})
        return OrderSchema.model_validate(updated_db_order)

    async def create_order_item(self, order_id: UUID, order_data: CreateOrder) -> list[OrderItemBase]:
        """Delegate to OrderItemService to create items for an existing order."""
        return await self.order_item_service.create_order_items(order_id, order_data)

    async def create_order_address(self, order_data: CreateOrder) -> OrderAddressBase:
        """Delegate to OrderAddressService to create an address for an order."""
        return await self.order_address_service.create_order_address(order_data)

    async def get_orders(self) -> list[OrderSchema]:
        db_orders = await self.repository.get_all()
        if not db_orders:
            raise OrdersNotFoundError()
        return [OrderSchema.model_validate(order) for  order in db_orders]

    async def get_orders_by_user_id(self, user_id: UUID) -> list[OrderSchema]:
        db_orders = await self.repository.get_many_by_field(field_name="user_id", value=user_id)
        if not db_orders:
            raise OrdersNotFoundError()
        return [OrderSchema.model_validate(order) for order in db_orders]

    async def update_order(self, order_id: UUID, order_data: UpdateOrder) -> OrderSchema:
        update_fields = order_data.model_dump(exclude_unset=True)
        current_order = await self.repository.get_by_id(order_id)
        if not current_order:
            raise OrderNotFoundError(order_id)

        async with self.repository.session.begin_nested():
            updated_order = await self.repository.update_by_id(order_id, data=update_fields)

            status_transitioned_to_confirmed = (
                update_fields.get("status") == OrderStatus.CONFIRMED
                and current_order.status != OrderStatus.CONFIRMED
            )
            if status_transitioned_to_confirmed:
                await self.outbox_event_service.add_outbox_event(
                    event_type=OrderEvents.ORDER_CONFIRMED,
                    payload=OrderConfirmedEvent(
                        service=Services.ORDER_SERVICE,
                        event_type=OrderEvents.ORDER_CONFIRMED,
                        order_id=updated_order.id,
                        user_id=updated_order.user_id,
                        user_email=updated_order.user_email,
                    ),
                )

        if not updated_order:
            raise OrderNotFoundError(order_id)
        return OrderSchema.model_validate(updated_order)

    async def delete_order_by_id(self, order_id: UUID) -> None:
        deleted = await self.repository.delete_by_id(order_id)
        if not deleted:
            raise OrderNotFoundError(order_id)
