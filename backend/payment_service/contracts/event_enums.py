from enum import StrEnum


class OrderEvents(StrEnum):
    ORDER_CANCELLED = "order.cancelled"


class PaymentEvents(StrEnum):
    # The card is authorized (funds held, not yet charged).
    PAYMENT_AUTHORIZED = "payment.authorized"
    # The authorized amount was captured: the customer is actually charged.
    PAYMENT_SUCCEEDED = "payment.succeeded"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"
    PAYMENT_CANCELLED = "payment.cancelled"
    # One word after "payment." so order-service's "payment.*" binding matches it.
    PAYMENT_REFUND_FAILED = "payment.refund_failed"
    # A customer disputed the charge with their bank (a chargeback).
    PAYMENT_DISPUTE_OPENED = "payment.dispute_opened"
    PAYMENT_DISPUTE_CLOSED = "payment.dispute_closed"


class PaymentCommands(StrEnum):
    """Instructions order_service sends payment_service about a held card.

    They travel on the order exchange under "payment.*.requested" keys, which
    match none of the "order.#", "order.*", "cj.order.*" or "production.job.#"
    bindings there, so only payment_service's own queue receives them.
    """

    CAPTURE_REQUESTED = "payment.capture.requested"
    RELEASE_REQUESTED = "payment.release.requested"
    # Give back part of a payment (lines, maybe shipping) — admin-driven.
    REFUND_REQUESTED = "payment.refund.requested"
