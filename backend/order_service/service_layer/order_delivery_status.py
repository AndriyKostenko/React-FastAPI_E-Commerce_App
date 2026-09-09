"""Derives one order-level delivery status from its per-line fulfillment states."""

from collections.abc import Iterable

from models.order_fulfillment_models import OrderLineFulfillment
from shared.enums.status_enums import LineFulfillmentStatus, OrderDeliveryStatus


class OrderDeliveryStatusAggregator:
    """Folds per-line progress into the single status the customer is shown.

    A cart can mix a CJ-dropshipped line, a catalog line posted from local
    stock, and a custom line printed in-house. Each moves on its own clock, so
    marking the whole order "dispatched" the moment any one line ships would
    tell the customer their unprinted T-shirt is on its way. The order is only
    as far along as its least advanced line that still owes something.
    """

    def aggregate(
        self, lines: Iterable[OrderLineFulfillment]
    ) -> OrderDeliveryStatus | None:
        """Return the order status these lines imply, or None when unknown.

        ``None`` means there is nothing to derive from — an order with no line
        snapshots at all — and the caller should leave the stored status alone
        rather than resetting it.
        """
        statuses = [LineFulfillmentStatus(line.status) for line in lines]
        if not statuses:
            return None

        outstanding = [
            status
            for status in statuses
            if status != LineFulfillmentStatus.CANCELLED
        ]
        if not outstanding:
            return OrderDeliveryStatus.CANCELLED

        if all(status == LineFulfillmentStatus.DELIVERED for status in outstanding):
            return OrderDeliveryStatus.DELIVERED

        # Dispatched means "something is genuinely on its way and nothing is
        # still waiting to be made", so a printed-but-unposted line holds the
        # order back exactly like a queued one.
        if all(
            status in LineFulfillmentStatus.dispatched() for status in outstanding
        ):
            return OrderDeliveryStatus.DISPATCHED

        return OrderDeliveryStatus.PENDING
