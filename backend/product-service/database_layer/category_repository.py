from sqlalchemy.ext.asyncio import AsyncSession

from models.category_models import ProductCategory
from shared.database_layer import BaseRepository


class CategoryRepository(BaseRepository[ProductCategory]):
    """
    This class extends BaseRepository to provide specific methods
    for managing categories in the database.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, ProductCategory)

