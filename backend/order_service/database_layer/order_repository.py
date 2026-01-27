from sqlalchemy.ext.asyncio import AsyncSession

from models.order_models import Order
from shared.database_layer import BaseRepository


class OrderRepository(BaseRepository[Order]):
    """
    This class extends BaseRepository to provide specific methods
    for managing orders in the database.
    """
    def __init__(self, session: AsyncSession):
        super().__init__(session, Order)
