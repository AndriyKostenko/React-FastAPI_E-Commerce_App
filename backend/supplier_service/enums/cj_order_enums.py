"""Lifecycle vocabularies for the CJ Dropshipping order boundary."""

from enum import StrEnum


class CJOrderAttemptStatus(StrEnum):
    """Local state of one order's CJ fulfillment boundary.

    ``CREATING`` is the durable marker written *before* the non-transactional
    POST to CJ, so a crashed worker can tell "never submitted" from "outcome
    unknown" on restart.
    """

    CREATING = "creating"
    CREATED = "created"
    # Confirmed at CJ (CJ status UNPAID) but not yet paid.
    CONFIRMED = "confirmed"
    # Confirmed, but the CJ balance cannot cover the bill yet.
    AWAITING_FUNDS = "awaiting_funds"
    # Paid from the CJ balance: CJ will now fulfil it.
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    RECONCILIATION_REQUIRED = "reconciliation_required"

    @classmethod
    def awaiting_payment(cls) -> frozenset["CJOrderAttemptStatus"]:
        """Statuses whose CJ order exists but has not been paid for yet."""
        return frozenset({cls.CREATED, cls.CONFIRMED, cls.AWAITING_FUNDS})

    @classmethod
    def open_for_tracking(cls) -> frozenset["CJOrderAttemptStatus"]:
        """Statuses whose CJ order can still change and is worth polling.

        An unpaid order never ships, so tracking starts once it is paid.
        """
        return frozenset({cls.PAID, cls.SHIPPED})

    @classmethod
    def terminal(cls) -> frozenset["CJOrderAttemptStatus"]:
        """Statuses that no CJ poll can move any further."""
        return frozenset({cls.DELIVERED, cls.FAILED, cls.CANCELLED, cls.REJECTED})


class CJRemoteOrderStatus(StrEnum):
    """The lifecycle CJ's own order status strings are mapped onto."""

    PENDING = "pending"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"
