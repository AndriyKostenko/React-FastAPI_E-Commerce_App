from enum import StrEnum


class OrderSagaResponseQueue(StrEnum):
    ORDER_SAGA_RESPONSE_QUEUE = "order.saga.response"
    ORDER_SAGA_RESPONSE_DEAD_LETTER_QUEUE = "order.saga.response.dlq"


class InventoryEvents(StrEnum):
    INVENTORY_RESERVE_SUCCEEDED = "inventory.reserve.succeeded"
    INVENTORY_RESERVE_FAILED = "inventory.reserve.failed"
    INVENTORY_RESERVE_REQUESTED = "inventory.reserve.requested"
    INVENTORY_RELEASE_REQUESTED = "inventory.release.requested"


class OrderEvents(StrEnum):
    ORDER_CREATED = "order.created"
    ORDER_CONFIRMED = "order.confirmed"
    ORDER_CANCELLED = "order.cancelled"
    CJ_ORDER_CREATED = "cj.order.created"
    CJ_ORDER_FAILED = "cj.order.failed"
    # CJ accepted and was paid for the order from our balance: the goods are
    # committed, so the customer's authorized card can now be captured.
    CJ_ORDER_PAID = "cj.order.paid"
    CJ_ORDER_SHIPPED = "cj.order.shipped"
    CJ_ORDER_DELIVERED = "cj.order.delivered"
    # Customer returns. Three segments on purpose: notification-service's
    # "order.#" binding matches them, the "order.*" bindings of shipping- and
    # cart-service do not.
    RETURN_REQUESTED = "order.return.requested"
    RETURN_APPROVED = "order.return.approved"
    RETURN_REJECTED = "order.return.rejected"
    # A return's refund went through at the card (payment-service confirmed it).
    RETURN_REFUNDED = "order.return.refunded"


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


class ShippingEvents(StrEnum):
    SHIPMENT_CREATED = "shipment.created"
    SHIPMENT_SHIPPED = "shipment.shipped"
    SHIPMENT_DELIVERED = "shipment.delivered"
    SHIPMENT_CANCELLED = "shipment.cancelled"


class ProductionEvents(StrEnum):
    """In-house print-and-post fulfillment lifecycle (routing key "production.job.*").

    These share the order exchange with the "order.*" and "cj.order.*" keys but
    match neither binding, so each consumer that wants them binds its own queue.
    """

    PRODUCTION_JOB_STARTED = "production.job.started"
    PRODUCTION_JOB_PRINTED = "production.job.printed"
    PRODUCTION_JOB_SHIPPED = "production.job.shipped"
    PRODUCTION_JOB_DELIVERED = "production.job.delivered"
    PRODUCTION_JOB_CANCELLED = "production.job.cancelled"


class ArtworkEvents(StrEnum):
    """Retention markers linking a paid order line to its stored print file.

    product_service owns the artwork object but order_service owns the
    reference, so these events are what let a cleanup job tell a paid order's
    print file from an abandoned generation draft.
    """

    ARTWORK_RETAINED = "artwork.retained"
    ARTWORK_RELEASED = "artwork.released"
