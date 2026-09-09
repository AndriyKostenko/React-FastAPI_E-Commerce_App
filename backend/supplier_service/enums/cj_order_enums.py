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
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    RECONCILIATION_REQUIRED = "reconciliation_required"

    @classmethod
    def open_for_tracking(cls) -> frozenset["CJOrderAttemptStatus"]:
        """Statuses whose CJ order can still change and is worth polling."""
        return frozenset({cls.CREATED, cls.SHIPPED})

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
