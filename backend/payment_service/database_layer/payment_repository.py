from sqlalchemy.ext.asyncio import AsyncSession

from models.payment_models import Payment
from shared.database_layer.database_layer import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    """Repository for CRUD operations on Payment records."""
    def __init__(self, session: AsyncSession):
        super().__init__(session, Payment)
