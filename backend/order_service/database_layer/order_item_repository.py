from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models.order_item_models import OrderItem
from shared.database_layer.database_layer import BaseRepository


class OrderItemRepository(BaseRepository[OrderItem]):
    """
    This class extends BaseRepository to provide specific methods
    for managing order items in the database.
    """
    def __init__(self, session: AsyncSession):
        super().__init__(session, OrderItem)

    async def get_by_order_id_with_fulfillment(self, order_id):
        result = await self.session.execute(
            select(OrderItem)
            .where(OrderItem.order_id == order_id)
            .options(selectinload(OrderItem.fulfillment))
            .order_by(OrderItem.date_created, OrderItem.id)
        )
        return list(result.scalars().all())
