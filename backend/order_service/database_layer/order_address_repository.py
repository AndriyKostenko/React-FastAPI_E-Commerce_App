from sqlalchemy.ext.asyncio import AsyncSession

from models.order_address_models import OrderAddress
from shared.database_layer import BaseRepository


class OrderAddressRepository(BaseRepository[OrderAddress]):
    """
    This class extends BaseRepository to provide specific methods
    for managing order adress in the database.
    """
    def __init__(self, session: AsyncSession):
        super().__init__(session, OrderAddress)
