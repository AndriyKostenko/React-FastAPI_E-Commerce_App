from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select

from enums.cj_order_enums import CJOrderAttemptStatus
from models.cj_order_attempt_models import CJOrderAttempt
from infrastructure.database_layer.database_layer import BaseRepository


class CJOrderAttemptRepository(BaseRepository[CJOrderAttempt]):
    def __init__(self, session):
        super().__init__(session=session, model=CJOrderAttempt)

    async def ended_with_personal_data(self, ended_before: datetime, limit: int) -> list[CJOrderAttempt]:
        """Ended orders (terminal status) still holding the customer's details, ended before the cutoff.

        Delivery is when a delivered order ended; for one that failed, was
        cancelled or rejected, its last change. Row-locked, so two runs never
        handle the same order.
        """
        ended_at = func.coalesce(CJOrderAttempt.delivered_at, CJOrderAttempt.date_updated)
        result = await self.session.execute(
            select(CJOrderAttempt)
            .where(
                CJOrderAttempt.status.in_([status.value for status in CJOrderAttemptStatus.terminal()]),
                CJOrderAttempt.personal_data_removed_at.is_(None),
                ended_at < ended_before,
            )
            .order_by(ended_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def get_for_update(self, order_id: UUID) -> CJOrderAttempt | None:
        result = await self.session.execute(
            select(CJOrderAttempt)
            .where(CJOrderAttempt.order_id == order_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def claim_due_for_tracking(
        self,
        *,
        due_before: datetime,
        created_after: datetime,
        limit: int,
        statuses: Iterable[str] = CJOrderAttemptStatus.open_for_tracking(),
    ) -> list[CJOrderAttempt]:
        """Lock the open CJ orders whose tracking state is due for a refresh.

        ``skip_locked`` lets several poller processes share the backlog without
        blocking each other or polling the same CJ order twice.
        """
        result = await self.session.execute(
            select(CJOrderAttempt)
            .where(
                CJOrderAttempt.status.in_([str(status) for status in statuses]),
                CJOrderAttempt.cj_order_number.is_not(None),
                CJOrderAttempt.date_created >= created_after,
                or_(
                    CJOrderAttempt.last_polled_at.is_(None),
                    CJOrderAttempt.last_polled_at <= due_before,
                ),
            )
            .order_by(CJOrderAttempt.last_polled_at.asc().nulls_first())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def get_due_for_payment(
        self, *, updated_before: datetime, limit: int
    ) -> list[CJOrderAttempt]:
        """Unpaid CJ orders not touched since ``updated_before``, oldest first.

        The gap keeps the retry task off an order the event consumer is still
        paying for the first time.
        """
        result = await self.session.execute(
            select(CJOrderAttempt)
            .where(
                CJOrderAttempt.status.in_(
                    [str(status) for status in CJOrderAttemptStatus.awaiting_payment()]
                ),
                CJOrderAttempt.cj_order_number.is_not(None),
                CJOrderAttempt.cancelled_at.is_(None),
                CJOrderAttempt.date_updated <= updated_before,
            )
            .order_by(CJOrderAttempt.date_updated.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
