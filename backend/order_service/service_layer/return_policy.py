"""
What a return may be, per way a line was fulfilled (Strategy).

The rules differ because the goods differ: a garment printed for one customer
cannot be resold, and a dropshipped item costs more to send back to the
supplier than it is worth. Changing the policy for one channel means changing
one class here; the return service only asks.
"""

from abc import ABC, abstractmethod

from shared.contracts.order import FulfillmentType
from shared.contracts.returns import ReturnFault, ReturnReason


class ReturnPolicy(ABC):
    @abstractmethod
    def allows(self, fault: ReturnFault) -> bool:
        """Whether a return for this fault is accepted at all."""

    @abstractmethod
    def ships_back(self, fault: ReturnFault) -> bool:
        """False: refunded without the goods coming back (returnless)."""

    def refunds_shipping(self, fault: ReturnFault) -> bool:
        return fault is ReturnFault.SELLER

    def requires_photo(self, fault: ReturnFault) -> bool:
        return fault is ReturnFault.SELLER

    def allowed_reasons(self) -> list[ReturnReason]:
        return [reason for reason in ReturnReason if self.allows(reason.fault)]


class CustomPrintReturnPolicy(ReturnPolicy):
    """Made to order: only our mistakes, and the garment stays with the customer."""

    def allows(self, fault: ReturnFault) -> bool:
        return fault is ReturnFault.SELLER

    def ships_back(self, fault: ReturnFault) -> bool:
        return False


class DropshipReturnPolicy(ReturnPolicy):
    """
    A defect is refunded without the item coming back (the cost is claimed
    from the supplier); a change of mind comes back to the local address at
    the customer's cost.
    """

    def allows(self, fault: ReturnFault) -> bool:
        return True

    def ships_back(self, fault: ReturnFault) -> bool:
        return fault is ReturnFault.CUSTOMER


class LocalStockReturnPolicy(ReturnPolicy):
    """Ordinary retail: everything comes back to the warehouse."""

    def allows(self, fault: ReturnFault) -> bool:
        return True

    def ships_back(self, fault: ReturnFault) -> bool:
        return True


class ReturnPolicies:
    """The policy for each fulfilment type."""

    def __init__(self, policies: dict[FulfillmentType, ReturnPolicy] | None = None) -> None:
        self._policies: dict[FulfillmentType, ReturnPolicy] = dict(policies or {
            "custom": CustomPrintReturnPolicy(),
            "cj": DropshipReturnPolicy(),
            "catalog": LocalStockReturnPolicy(),
        })

    def for_type(self, fulfillment_type: str) -> ReturnPolicy:
        for known, policy in self._policies.items():
            if known == fulfillment_type:
                return policy
        raise ValueError(f"No return policy for fulfilment type {fulfillment_type!r}")
