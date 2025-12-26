from sqlalchemy.ext.asyncio import AsyncSession

from shared.database_layer import BaseRepository # type: ignore
from models.product_image_models import ProductImage



class ProductImageRepository(BaseRepository[ProductImage]):
    """
    This class extends BaseRepository to provide specific methods
    for managing product images in the database.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, ProductImage)
