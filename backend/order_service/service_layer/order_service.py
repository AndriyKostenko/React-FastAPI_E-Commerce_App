from uuid import UUID
from enum import Enum

from service_layer.order_address_service import OrderAddressService
from service_layer.order_item_service import OrderItemService
from database_layer.order_repository import OrderRepository
from models.order_models import Order
from shared.schemas.order_schemas import CreateOrder, OrderItemBase, OrderSchema, OrderAddressBase
from exceptions.order_exceptions import OrderNotFoundError


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class OrderService:
    """Service layer for order management operations, business logic, data validation."""
    def __init__(self, repository: OrderRepository, order_item_service: OrderItemService, order_address_service: OrderAddressService):
        self.repository: OrderRepository = repository
        self.order_item_service: OrderItemService = order_item_service
        self.order_address_service:OrderAddressService = order_address_service

    async def create_order(self, order_data: CreateOrder) -> tuple[OrderSchema, list[OrderItemBase]]:
        """
        Creating new order and initiating the SAGA pattern.
        The order status is "pending" untill the inventory is confirmed
        """
        # creating an order address
        new_db_order_address: OrderAddressBase = await self.order_address_service.create_order_address(order_data)
        # creating order
        new_db_order: Order = await self.repository.create(
            Order(
                user_id=order_data.user_id,
                amount=order_data.amount,
                currency=order_data.currency,
                status=OrderStatus.PENDING,
                delivery_status=order_data.delivery_status,
                payment_intent_id=order_data.payment_intent_id,
                address_id=new_db_order_address.id
            )
        )
        # creating order items
        new_db_order_items: list[OrderItemBase]  = await self.order_item_service.create_order_items(new_db_order.id, order_data)
        return OrderSchema.model_validate(new_db_order), new_db_order_items

    async def cancel_order(self):
       pass

    async def get_order_by_id(self, order_id: UUID) -> OrderSchema:
        db_order = await self.repository.get_by_id(order_id)
        if not db_order:
            raise OrderNotFoundError(order_id)
        return OrderSchema.model_validate(db_order)

    async def update_order_status(self, order_id: UUID, order_status: OrderStatus) -> OrderSchema:
        update_dict = {"status": order_status}
        updated_db_order = await self.repository.update_by_id(order_id, **update_dict)
        return OrderSchema.model_validate(updated_db_order)

    async def create_order_item(self, order_item_data):
        pass

    async def create_order_address(self, order_address_data):
        pass
