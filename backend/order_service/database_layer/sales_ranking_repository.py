from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.status_enums import OrderStatus
from models.order_fulfillment_models import OrderLineFulfillment
from models.order_item_models import OrderItem
from models.order_models import Order
from models.order_refund_models import OrderRefund
from infrastructure.database_layer.database_layer import BaseRepository


@dataclass(frozen=True, slots=True)
class SoldLine:
    """One order line of a paid order: what was bought, and how many."""

    order_item_id: UUID
    product_id: UUID
    quantity: int


class SalesRankingRepository(BaseRepository[OrderItem]):
    """Reads the paid order lines and the refunds against them since a cutoff."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, OrderItem)

    async def sold_lines_since(self, cutoff: datetime, *, exclude_fulfillment: str) -> list[SoldLine]:
        """Lines of confirmed (paid) orders placed at or after ``cutoff``.

        A line with no fulfillment row predates per-line routing and is a
        catalogue line, so it is kept.
        """
        result = await self.session.execute(
            select(OrderItem.id, OrderItem.product_id, OrderItem.quantity)
            .join(Order, Order.id == OrderItem.order_id)
            .outerjoin(OrderLineFulfillment, OrderLineFulfillment.order_item_id == OrderItem.id)
            .where(
                Order.status == OrderStatus.CONFIRMED,
                Order.date_created >= cutoff,
                or_(
                    OrderLineFulfillment.fulfillment_type.is_(None),
                    OrderLineFulfillment.fulfillment_type != exclude_fulfillment,
                ),
            )
        )
        return [SoldLine(order_item_id=row.id, product_id=row.product_id, quantity=row.quantity) for row in result]

    async def refunded_units_since(self, cutoff: datetime, *, exclude_status: str) -> Counter[UUID]:
        """Units refunded per order line, for orders placed at or after ``cutoff``.

        Refunds in ``exclude_status`` (the failed ones, which gave nothing back)
        are left out.
        """
        result = await self.session.execute(
            select(OrderRefund.lines)
            .join(Order, Order.id == OrderRefund.order_id)
            .where(
                Order.date_created >= cutoff,
                OrderRefund.status != exclude_status,
            )
        )
        refunded: Counter[UUID] = Counter()
        # ``lines`` is a JSON list: [{"order_item_id": str, "quantity": int, "amount": str}]
        for lines in result.scalars():
            for line in lines:
                refunded[UUID(str(line["order_item_id"]))] += int(line["quantity"])
        return refunded
