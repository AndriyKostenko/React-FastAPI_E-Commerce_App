"""Customer returns: the vocabulary order-service and notification-service share.

The customer picks a reason; whose fault it is follows from the reason, never
from the customer. Fault decides who pays: the seller's fault is refunded in
full (shipping included) and needs a photo, a change of mind is not.
"""

from enum import StrEnum

from pydantic import BaseModel


class ReturnFault(StrEnum):
    SELLER = "seller"
    CUSTOMER = "customer"


class ReturnReason(StrEnum):
    DEFECTIVE = "defective"
    DAMAGED = "damaged"
    WRONG_ITEM = "wrong_item"
    MISPRINT = "misprint"
    CHANGED_MIND = "changed_mind"
    DOES_NOT_FIT = "does_not_fit"

    @property
    def fault(self) -> ReturnFault:
        if self in _SELLER_FAULT_REASONS:
            return ReturnFault.SELLER
        return ReturnFault.CUSTOMER

    @classmethod
    def for_fault(cls, fault: ReturnFault) -> list["ReturnReason"]:
        return [reason for reason in cls if reason.fault is fault]


_SELLER_FAULT_REASONS = frozenset({
    ReturnReason.DEFECTIVE,
    ReturnReason.DAMAGED,
    ReturnReason.WRONG_ITEM,
    ReturnReason.MISPRINT,
})


class ReturnStatus(StrEnum):
    """
    requested -> approved -> completed   (goods came back, or none had to)
    requested -> rejected | cancelled    (admin said no / customer withdrew)
    approved  -> rejected                (goods never arrived or failed inspection)
    """

    REQUESTED = "requested"
    APPROVED = "approved"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

    @classmethod
    def open(cls) -> frozenset["ReturnStatus"]:
        """Statuses whose not-yet-refunded units are still spoken for."""
        return frozenset({cls.REQUESTED, cls.APPROVED})


class ReturnLineSummary(BaseModel):
    """One returned line, as the customer and admin emails describe it."""

    product_name: str
    quantity: int
    ships_back: bool
