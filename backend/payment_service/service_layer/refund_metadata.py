"""The marker this service puts on every Stripe refund it creates."""

from uuid import UUID


class AppRefundMetadata:
    """
    Tells the refunds this service made from those made elsewhere.

    Stripe reports every refund back through ``charge.refund.updated``,
    including our own. The code path that created a refund records it itself,
    and the webhook can arrive before that record is committed, so only a
    marker carried by the refund itself can tell the webhook to leave it alone.
    """

    KEY = "refund_origin"
    VALUE = "payment-service"

    @classmethod
    def for_order(cls, order_id: UUID, refund_id: UUID | None = None) -> dict[str, str]:
        metadata = {cls.KEY: cls.VALUE, "order_id": str(order_id)}
        if refund_id is not None:
            metadata["refund_id"] = str(refund_id)
        return metadata

    @classmethod
    def is_ours(cls, metadata: dict[str, str] | None) -> bool:
        return (metadata or {}).get(cls.KEY) == cls.VALUE
