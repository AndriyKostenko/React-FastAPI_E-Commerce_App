from ctypes import addressof
from enum import Enum
from locale import currency

from database_layer.order_repository import OrderRepository
from models.order_models import Order, OrderItem, OrderAddress
from shared.schemas.order_schemas import CreateOrder, OrderSchema
from event_publisher.order_event_publisher import order_event_publisher


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class OrderService:
    """Service layer for order management operations, business logic and data validation."""
    def __init__(self, repository: OrderRepository):
        self.repository: OrderRepository = repository

    async def create_order(self, order_data: CreateOrder) -> OrderSchema:
        """
        Creating new order and initiating the SAGA pattern.
        The order status is pending untill the inventory is confirmed
        """
        
        
        # creating an order address
        new_order_adress = OrderAddress(
            user_id=order_data.user_id,
            street=order_data.address.street,
            city=order_data.address.city,
            province=order_data.address.province,
            postal_code=order_data.address.postal_code
        )
        db_new_order_adress: OrderAddress = await self.repository.create(new_order_adress)
        
        # creating order
        order_data.status = OrderStatus.PENDING
        new_order = Order(
            user_id=order_data.user_id,
            amount=order_data.amount,
            currency=order_data.currency,
            status=order_data.status,
            delivery_status=order_data.delivery_status,
            payment_intent_id=order_data.payment_intent_id,
            address_id=db_new_order_adress.id
        )
        db_order: Order = await self.repository.create(new_order)
        
        # creating order items
        new_order_items = [
            OrderItem(
                order_id=db_order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price=item.price
            )
            for item in order_data.products
        ]
        db_order_items: OrderItem = await self.repository.create_many(new_order_items)
        
        # converting order items to event items
        event_items = [
            OrderItem(
                product_id=item.id,
                quantity=item.quantity,
                price=item.price
            )
            for item in order_data.products
        ]
        
        # publishing order created event
        await order_event_publisher.publish_order_created(
            order_id=new_order.id,
            user_id=new_order.user_id,
            items=event_items,
            total_amount=new_order.total_amount
        )
        
        # request inventory reservation (start SAGA)
        await order_event_publisher.publish_inventory_reserve_requested(
            order_id=new_order.id,
            items=event_items,
            user_id=new_order.user_id
        )
        return OrderSchema.model_validate(new_order)
        
        
    async def create_order_item(self, order_item_data):
        pass

    async def create_order_address(self, order_address_data):
        pass