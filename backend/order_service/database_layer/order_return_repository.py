from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.order_return_models import ReturnRequest
from shared.contracts.returns import ReturnStatus
from shared.database_layer.database_layer import BaseRepository


class ReturnRequestRepository(BaseRepository[ReturnRequest]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, ReturnRequest)

    async def list_for_order(self, order_id: UUID) -> list[ReturnRequest]:
        result = await self.session.execute(
            select(ReturnRequest)
            .where(ReturnRequest.order_id == order_id)
            .order_by(ReturnRequest.date_created)
        )
        return list(result.scalars().all())

    async def list_by_status(self, status: ReturnStatus | None, *, limit: int, offset: int) -> list[ReturnRequest]:
        """The admin queue, oldest first so nothing waits forever."""
        query = select(ReturnRequest).order_by(ReturnRequest.date_created).limit(limit).offset(offset)
        if status is not None:
            query = query.where(ReturnRequest.status == status)
        result = await self.session.execute(query)
        return list(result.scalars().all())
