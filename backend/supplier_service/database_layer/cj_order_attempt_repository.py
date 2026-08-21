from uuid import UUID

from sqlalchemy import select

from models.cj_order_attempt_models import CJOrderAttempt
from shared.database_layer.database_layer import BaseRepository


class CJOrderAttemptRepository(BaseRepository[CJOrderAttempt]):
    def __init__(self, session):
        super().__init__(session=session, model=CJOrderAttempt)

    async def get_for_update(self, order_id: UUID) -> CJOrderAttempt | None:
        result = await self.session.execute(
            select(CJOrderAttempt)
            .where(CJOrderAttempt.order_id == order_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

