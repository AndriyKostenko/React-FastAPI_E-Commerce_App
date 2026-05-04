from uuid import UUID

from database_layer.order_item_repository import OrderItemRepository
from models.order_item_models import OrderItem
from shared.schemas.order_schemas import CreateOrder, OrderItemBase


class OrderItemService:
    def __init__(self, repository: OrderItemRepository) -> None:
        self.repository: OrderItemRepository = repository

    async def create_order_items(self, db_order_id: UUID, order_data: CreateOrder) -> list[OrderItemBase]:
        new_order_items = [
            OrderItem(
                order_id=db_order_id,
                product_id=item.id,
                quantity=item.quantity,
                price=item.price
            )
            for item in order_data.products
        ]
        new_db_order_items = await self.repository.create_many(new_order_items)
        return [OrderItemBase.model_validate(order_item) for order_item in new_db_order_items]

    async def get_items_by_order_id(self, order_id: UUID) -> list[OrderItemBase]:
        items = await self.repository.get_many_by_field(field_name="order_id", value=order_id)
        return [OrderItemBase.model_validate(item) for item in (items or [])]
