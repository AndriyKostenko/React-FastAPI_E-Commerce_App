from enum import StrEnum


class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class OrderDeliveryStatus(StrEnum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

class SyncStatus(StrEnum):
	RUNNING = "running"
	COMPLETED = "completed"
	FAILED = "failed"


class LineFulfillmentStatus(StrEnum):
    """Progress of one order line, aggregated into ``Order.delivery_status``.

    An order can mix a CJ-dropshipped line, a catalog line shipped from the
    local warehouse, and a custom line printed in-house. Each moves on its own
    clock, so the per-line status is the source of truth and the order-level
    delivery status is derived from it.
    """

    PENDING = "pending"
    QUEUED = "queued"
    IN_PRODUCTION = "in_production"
    PRINTED = "printed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

    @classmethod
    def dispatched(cls) -> frozenset["LineFulfillmentStatus"]:
        """Statuses meaning the goods have physically left."""
        return frozenset({cls.SHIPPED, cls.DELIVERED})

    @classmethod
    def terminal(cls) -> frozenset["LineFulfillmentStatus"]:
        """Statuses no further fulfillment event can move."""
        return frozenset({cls.DELIVERED, cls.CANCELLED})

    @classmethod
    def blocks_cancellation(cls) -> frozenset["LineFulfillmentStatus"]:
        """Statuses after which a self-serve cancellation must be refused.

        Once a garment is printed the materials are spent, and once it is
        posted the goods are gone; both need a human return decision rather
        than an automatic refund.
        """
        return frozenset({cls.PRINTED, cls.SHIPPED, cls.DELIVERED})


class ProductionJobStatus(StrEnum):
    """Lifecycle of one in-house print job on the operator's work queue."""

    QUEUED = "queued"
    IN_PRODUCTION = "in_production"
    PRINTED = "printed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"

    @classmethod
    def open_statuses(cls) -> frozenset["ProductionJobStatus"]:
        """Statuses still expecting operator action."""
        return frozenset({cls.QUEUED, cls.IN_PRODUCTION, cls.PRINTED, cls.ON_HOLD})

    @classmethod
    def terminal(cls) -> frozenset["ProductionJobStatus"]:
        """Statuses the queue never moves out of again."""
        return frozenset({cls.DELIVERED, cls.CANCELLED})

    @classmethod
    def needs_reconciliation_on_cancel(cls) -> frozenset["ProductionJobStatus"]:
        """Statuses whose cancellation must be reviewed before refunding.

        Printing consumes a blank garment and ink; shipping puts real goods in
        the post. Cancelling either without a human looking at it refunds money
        against stock that has already been spent or sent.
        """
        return frozenset({cls.PRINTED, cls.SHIPPED, cls.DELIVERED})

    @property
    def line_status(self) -> LineFulfillmentStatus:
        """The order-line status this production status projects onto."""
        return _PRODUCTION_TO_LINE_STATUS[self]


_PRODUCTION_TO_LINE_STATUS: dict[ProductionJobStatus, LineFulfillmentStatus] = {
    ProductionJobStatus.QUEUED: LineFulfillmentStatus.QUEUED,
    ProductionJobStatus.IN_PRODUCTION: LineFulfillmentStatus.IN_PRODUCTION,
    ProductionJobStatus.PRINTED: LineFulfillmentStatus.PRINTED,
    ProductionJobStatus.SHIPPED: LineFulfillmentStatus.SHIPPED,
    ProductionJobStatus.DELIVERED: LineFulfillmentStatus.DELIVERED,
    # A held job is still owed to the customer; it has not moved forward.
    ProductionJobStatus.ON_HOLD: LineFulfillmentStatus.QUEUED,
    ProductionJobStatus.CANCELLED: LineFulfillmentStatus.CANCELLED,
}
