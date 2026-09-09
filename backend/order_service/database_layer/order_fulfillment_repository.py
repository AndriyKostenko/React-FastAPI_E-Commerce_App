from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.order_fulfillment_models import CustomProductionJob, OrderLineFulfillment
from models.order_item_models import OrderItem
from models.order_models import Order
from shared.database_layer.database_layer import BaseRepository
from shared.enums.status_enums import ProductionJobStatus


class OrderLineFulfillmentRepository(BaseRepository[OrderLineFulfillment]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, OrderLineFulfillment)

    async def get_by_order_id(self, order_id: UUID) -> list[OrderLineFulfillment]:
        """Every line snapshot of one order, ordered-item join included.

        The order-level delivery status is derived from these rows, so the
        aggregation always reads the whole set rather than a single line.
        """
        result = await self.session.execute(
            select(OrderLineFulfillment)
            .join(OrderItem, OrderItem.id == OrderLineFulfillment.order_item_id)
            .where(OrderItem.order_id == order_id)
        )
        return list(result.scalars().all())


class CustomProductionJobRepository(BaseRepository[CustomProductionJob]):
    """Reads and writes the in-house print queue."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, CustomProductionJob)

    async def get_with_context(self, job_id: UUID) -> CustomProductionJob | None:
        """One job with the order, address, and line snapshot it is printed from."""
        result = await self.session.execute(self._context_query(job_id))
        return result.scalar_one_or_none()

    async def get_for_update(self, job_id: UUID) -> CustomProductionJob | None:
        """Lock one job row, loading the context a transition needs with it.

        The eager loads travel with the locking query rather than following it:
        once the row is in the session's identity map a later query will not
        populate its relationships, and touching them would then fall back to
        a lazy load that cannot run on an async session.

        ``FOR UPDATE`` applies to ``custom_production_jobs`` alone — the
        related rows are fetched by ``selectinload``'s separate, unlocked
        queries — so two operators cannot advance the same job at once
        without the lock spreading across the order.
        """
        result = await self.session.execute(
            self._context_query(job_id).with_for_update()
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _context_query(job_id: UUID):
        return (
            select(CustomProductionJob)
            .where(CustomProductionJob.id == job_id)
            .options(
                selectinload(CustomProductionJob.order).selectinload(Order.address),
                selectinload(CustomProductionJob.order_item).selectinload(
                    OrderItem.fulfillment
                ),
            )
        )

    async def list_queue(
        self,
        *,
        statuses: list[str] | None = None,
        order_id: UUID | None = None,
        reconciliation_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CustomProductionJob]:
        """The operator's work list, oldest first so orders are worked in turn."""
        query = (
            select(CustomProductionJob)
            .options(
                selectinload(CustomProductionJob.order).selectinload(Order.address),
                selectinload(CustomProductionJob.order_item).selectinload(
                    OrderItem.fulfillment
                ),
            )
            .order_by(CustomProductionJob.date_created.asc())
            .limit(limit)
            .offset(offset)
        )
        for condition in self._filters(statuses, order_id, reconciliation_only):
            query = query.where(condition)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_queue(
        self,
        *,
        statuses: list[str] | None = None,
        order_id: UUID | None = None,
        reconciliation_only: bool = False,
    ) -> int:
        query = select(func.count(CustomProductionJob.id))
        for condition in self._filters(statuses, order_id, reconciliation_only):
            query = query.where(condition)
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def count_by_status(self) -> dict[str, int]:
        """Queue depth per status, for the admin dashboard header."""
        result = await self.session.execute(
            select(CustomProductionJob.status, func.count(CustomProductionJob.id))
            .group_by(CustomProductionJob.status)
        )
        counts = {status: 0 for status in ProductionJobStatus}
        counts.update({row[0]: row[1] for row in result.all()})
        return counts

    @staticmethod
    def _filters(
        statuses: list[str] | None,
        order_id: UUID | None,
        reconciliation_only: bool,
    ) -> list:
        conditions = []
        if statuses:
            conditions.append(CustomProductionJob.status.in_(statuses))
        if order_id is not None:
            conditions.append(CustomProductionJob.order_id == order_id)
        if reconciliation_only:
            conditions.append(CustomProductionJob.reconciliation_required.is_(True))
        return conditions
