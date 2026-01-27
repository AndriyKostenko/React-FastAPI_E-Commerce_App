from sqlalchemy.ext.asyncio import AsyncSession

from models.order_item_models import OrderItem
from shared.database_layer import BaseRepository


class OrderItemRepository(BaseRepository[OrderItem]):
    """
    This class extends BaseRepository to provide specific methods
    for managing order items in the database.
    """
    def __init__(self, session: AsyncSession):
        super().__init__(session, OrderItem)
