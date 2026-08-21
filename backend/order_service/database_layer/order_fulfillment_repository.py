from sqlalchemy.ext.asyncio import AsyncSession

from models.order_fulfillment_models import CustomProductionJob, OrderLineFulfillment
from shared.database_layer.database_layer import BaseRepository


class OrderLineFulfillmentRepository(BaseRepository[OrderLineFulfillment]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, OrderLineFulfillment)


class CustomProductionJobRepository(BaseRepository[CustomProductionJob]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, CustomProductionJob)
