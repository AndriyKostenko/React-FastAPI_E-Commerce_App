from shared.database_layer import BaseRepository
from models.review_models import ProductReview
from sqlalchemy.ext.asyncio import AsyncSession


class ReviewRepository(BaseRepository[ProductReview]):
    """
    This class extends BaseRepository to provide specific methods
    for managing product reviews in the database.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, ProductReview)
