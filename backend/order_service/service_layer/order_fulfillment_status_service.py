"""Keeps ``Order.delivery_status`` in step with its per-line fulfillment states."""

from uuid import UUID

from database_layer.order_fulfillment_repository import OrderLineFulfillmentRepository
from database_layer.order_repository import OrderRepository
from models.order_fulfillment_models import OrderLineFulfillment
from models.order_models import Order
from service_layer.order_delivery_status import OrderDeliveryStatusAggregator
from shared.enums.status_enums import LineFulfillmentStatus, OrderStatus


class OrderFulfillmentStatusService:
    """Records per-line progress and re-derives the order-level status.

    Every fulfillment channel reports at a different granularity: CJ and the
    local warehouse announce progress for a whole order, while the in-house
    print queue reports one garment at a time. All of them land here, so the
    order-level status is derived once, in one place, from the full set of
    lines rather than being overwritten by whichever channel reported last.
    """

    def __init__(
        self,
        order_repository: OrderRepository,
        fulfillment_repository: OrderLineFulfillmentRepository,
        aggregator: OrderDeliveryStatusAggregator | None = None,
    ) -> None:
        self.order_repository = order_repository
        self.fulfillment_repository = fulfillment_repository
        self.aggregator = aggregator or OrderDeliveryStatusAggregator()

    async def get_lines(self, order_id: UUID) -> list[OrderLineFulfillment]:
        return await self.fulfillment_repository.get_by_order_id(order_id)

    async def mark_lines(
        self,
        order: Order,
        status: LineFulfillmentStatus,
        *,
        fulfillment_types: set[str] | None = None,
        order_item_ids: set[UUID] | None = None,
    ) -> Order:
        """Advance the selected lines, then re-derive the order status.

        Selection is by fulfillment channel, by explicit line, or both. A line
        that has already reached a terminal state is left alone so a late
        duplicate event cannot walk a delivered parcel backwards.
        """
        lines = await self.get_lines(order.id)
        for line in lines:
            if fulfillment_types and line.fulfillment_type not in fulfillment_types:
                continue
            if order_item_ids and line.order_item_id not in order_item_ids:
                continue
            if LineFulfillmentStatus(line.status) in LineFulfillmentStatus.terminal():
                continue
            line.status = status
            await self.fulfillment_repository.update(line)

        return await self.refresh_delivery_status(order, lines)

    async def refresh_delivery_status(
        self,
        order: Order,
        lines: list[OrderLineFulfillment] | None = None,
    ) -> Order:
        """Recompute ``Order.delivery_status`` from the current line states."""
        if lines is None:
            lines = await self.get_lines(order.id)

        derived = self.aggregator.aggregate(lines)
        if derived is None:
            return order

        # A cancelled order keeps its cancelled delivery status: the lines say
        # where the goods got to, not whether the order still stands.
        if order.status == OrderStatus.CANCELLED:
            return order

        if order.delivery_status != derived:
            order.delivery_status = derived
            await self.order_repository.update(order)
        return order

    async def has_blocking_lines(self, order_id: UUID) -> bool:
        """True when some line is too far along to cancel and refund freely."""
        lines = await self.get_lines(order_id)
        return any(line.blocks_cancellation for line in lines)
