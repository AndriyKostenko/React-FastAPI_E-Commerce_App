from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.order_refund_models import OrderRefund
from shared.database_layer.database_layer import BaseRepository


class OrderRefundRepository(BaseRepository[OrderRefund]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, OrderRefund)

    async def list_for_order(self, order_id: UUID) -> list[OrderRefund]:
        result = await self.session.execute(
            select(OrderRefund).where(OrderRefund.order_id == order_id).order_by(OrderRefund.date_created)
        )
        return list(result.scalars().all())
