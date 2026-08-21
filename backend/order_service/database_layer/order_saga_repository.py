from uuid import UUID

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.order_saga_models import OrderSagaState
from models.order_models import Order
from shared.enums.status_enums import OrderStatus
from shared.database_layer.database_layer import BaseRepository


class OrderSagaRepository(BaseRepository[OrderSagaState]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, OrderSagaState)

    async def get_for_update(self, order_id: UUID) -> OrderSagaState | None:
        result = await self.session.execute(
            select(OrderSagaState)
            .where(OrderSagaState.order_id == order_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_expired_pending_for_update(
        self, cutoff: datetime, limit: int = 50
    ) -> list[tuple[OrderSagaState, Order]]:
        result = await self.session.execute(
            select(OrderSagaState, Order)
            .join(Order, Order.id == OrderSagaState.order_id)
            .where(
                Order.status == OrderStatus.PENDING,
                OrderSagaState.date_created < cutoff,
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.tuples().all())
