from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models.order_models import Order
from models.order_item_models import OrderItem
from shared.database_layer.database_layer import BaseRepository


class OrderRepository(BaseRepository[Order]):
    """
    This class extends BaseRepository to provide specific methods
    for managing orders in the database.
    """
    def __init__(self, session: AsyncSession):
        super().__init__(session, Order)

    async def get_with_fulfillment(self, order_id: UUID) -> Order | None:
        result = await self.session.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.items).selectinload(OrderItem.fulfillment),
                selectinload(Order.address),
            )
        )
        return result.scalar_one_or_none()

    async def delete_by_id(self, item_id: UUID) -> bool:
        """Delete an order and its items by eagerly loading the items first."""
        existing_obj = await self.get_by_id(item_id, load_relations=["items"])
        if existing_obj:
            await self.delete(existing_obj)
            return True
        return False
