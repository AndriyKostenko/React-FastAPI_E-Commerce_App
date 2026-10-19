from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from database_layer.sales_ranking_repository import SalesRankingRepository
from schemas.best_seller_schemas import BestSellerSchema
from service_layer.order_refund_service import RefundState


class BestSellerService:
    """
    Ranks catalogue products by the units customers kept.

    A unit counts when its order was paid (confirmed) inside the window, less
    every unit refunded against that line, returns included. Custom designs are
    left out: each is a one-off print on the same blank product, so ranking it
    would say nothing about what sells.
    """

    EXCLUDED_FULFILLMENT = "custom"

    def __init__(
        self,
        repository: SalesRankingRepository,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._clock = clock

    async def rank(self, *, days: int, limit: int) -> list[BestSellerSchema]:
        cutoff = self._clock() - timedelta(days=days)
        lines = await self._repository.sold_lines_since(cutoff, exclude_fulfillment=self.EXCLUDED_FULFILLMENT)
        # A requested refund counts already, as the return and refund paths count
        # it; only a failed one gave nothing back.
        refunded = await self._repository.refunded_units_since(cutoff, exclude_status=RefundState.FAILED)

        units: Counter[UUID] = Counter()
        for line in lines:
            # A refund never takes a line below zero, whatever was recorded.
            kept = line.quantity - min(refunded[line.order_item_id], line.quantity)
            if kept > 0:
                units[line.product_id] += kept

        # Most units first; the product id breaks ties so the order is stable
        # between requests (the gateway caches one answer for everybody).
        ranked = sorted(units.items(), key=lambda entry: (-entry[1], str(entry[0])))
        return [BestSellerSchema(product_id=product_id, units_sold=count) for product_id, count in ranked[:limit]]
