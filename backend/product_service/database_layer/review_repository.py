from sqlalchemy.ext.asyncio import AsyncSession

from shared.database_layer.database_layer import BaseRepository
from models.review_models import ProductReview


class ReviewRepository(BaseRepository[ProductReview]):
    """
    This class extends BaseRepository to provide specific methods
    for managing product reviews in the database.
    """
    def __init__(self, session: AsyncSession):
        super().__init__(session, ProductReview)
