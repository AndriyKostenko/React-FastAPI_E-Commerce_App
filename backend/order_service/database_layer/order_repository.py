from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from models.order_models import Order
from shared.database_layer.database_layer import BaseRepository


class OrderRepository(BaseRepository[Order]):
    """
    This class extends BaseRepository to provide specific methods
    for managing orders in the database.
    """
    def __init__(self, session: AsyncSession):
        super().__init__(session, Order)

    async def delete_by_id(self, item_id: UUID) -> bool:
        """Delete an order and its items by eagerly loading the items first."""
        existing_obj = await self.get_by_id(item_id, load_relations=["items"])
        if existing_obj:
            await self.delete(existing_obj)
            return True
        return False
