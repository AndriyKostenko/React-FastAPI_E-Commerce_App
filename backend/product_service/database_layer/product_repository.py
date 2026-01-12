from sqlalchemy.ext.asyncio import AsyncSession

from models.product_models import Product
from shared.database_layer import BaseRepository  #type: ignore


class ProductRepository(BaseRepository[Product]):
    """
    This class extends BaseRepository to provide specific methods
    for managing products in the database.
    """
    def __init__(self, session: AsyncSession):
        super().__init__(session, Product)
