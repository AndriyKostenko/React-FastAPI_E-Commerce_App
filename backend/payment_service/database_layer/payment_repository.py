from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.payment_models import Payment, PaymentDispute, PaymentRefund
from shared.database_layer.database_layer import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    """Repository for CRUD operations on Payment records."""
    def __init__(self, session: AsyncSession):
        super().__init__(session, Payment)

    async def get_by_order_for_update(self, order_id: UUID) -> Payment | None:
        """The order's payment, row-locked until the transaction ends."""
        result = await self.session.execute(
            select(Payment).where(Payment.order_id == order_id).with_for_update()
        )
        return result.scalar_one_or_none()


class PaymentRefundRepository(BaseRepository[PaymentRefund]):
    """Partial refunds, keyed by order_service's refund id."""
    def __init__(self, session: AsyncSession):
        super().__init__(session, PaymentRefund)


class PaymentDisputeRepository(BaseRepository[PaymentDispute]):
    """Chargebacks, keyed by Stripe's dispute id."""
    def __init__(self, session: AsyncSession):
        super().__init__(session, PaymentDispute)
