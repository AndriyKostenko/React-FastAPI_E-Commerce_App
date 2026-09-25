from uuid import UUID

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.order_saga_models import OrderSagaState
from models.order_fulfillment_models import OrderLineFulfillment
from models.order_item_models import OrderItem
from models.order_models import Order
from shared.enums.status_enums import LineFulfillmentStatus, OrderStatus
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

    async def get_stalled_supplier_orders_for_update(
        self, cutoff: datetime, limit: int = 50
    ) -> list[tuple[OrderSagaState, Order]]:
        """
        Confirmed orders CJ never took on: a CJ line is still waiting (CJ has
        not been paid for it) and the card is still only authorized, since
        before ``cutoff``.

        ``confirmed_at`` is null on orders confirmed before the column
        existed; their last saga update stands in for it.
        """
        waiting_cj_line = (
            select(OrderLineFulfillment.id)
            .join(OrderItem, OrderItem.id == OrderLineFulfillment.order_item_id)
            .where(
                OrderItem.order_id == Order.id,
                OrderLineFulfillment.fulfillment_type == "cj",
                OrderLineFulfillment.status.in_(
                    (LineFulfillmentStatus.PENDING, LineFulfillmentStatus.QUEUED)
                ),
            )
            .exists()
        )
        result = await self.session.execute(
            select(OrderSagaState, Order)
            .join(Order, Order.id == OrderSagaState.order_id)
            .where(
                Order.status == OrderStatus.CONFIRMED,
                OrderSagaState.payment_status == "authorized",
                func.coalesce(OrderSagaState.confirmed_at, OrderSagaState.date_updated) < cutoff,
                waiting_cj_line,
            )
            .limit(limit)
            .with_for_update(of=OrderSagaState, skip_locked=True)
        )
        return list(result.tuples().all())

    async def get_stale_uncaptured(
        self, cutoff: datetime, limit: int = 100
    ) -> list[OrderSagaState]:
        """Confirmed orders whose card is still only authorized since before ``cutoff``."""
        result = await self.session.execute(
            select(OrderSagaState)
            .join(Order, Order.id == OrderSagaState.order_id)
            .where(
                Order.status == OrderStatus.CONFIRMED,
                OrderSagaState.payment_status.in_(("authorized", "capture_requested")),
                OrderSagaState.date_updated < cutoff,
            )
            .limit(limit)
        )
        return list(result.scalars().all())
