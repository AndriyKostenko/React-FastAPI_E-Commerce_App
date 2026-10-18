from enum import StrEnum


class UserEventsQueue(StrEnum):
    USER_EVENTS_QUEUE = "user.events.queue"
    USER_EVENTS_DEAD_LETTER_QUEUE = "user.events.dlq"


class OrderEventsQueue(StrEnum):
    ORDER_EVENTS_QUEUE = "order.events.queue"
    ORDER_EVENTS_DEAD_LETTER_QUEUE = "order.events.dlq"
    # CJ fulfillment events (routing key "cj.order.*") travel on the same
    # order exchange but do NOT match the "order.#" binding above, so
    # notification_service binds them on a dedicated queue.
    NOTIFICATION_CJ_ORDER_EVENTS_QUEUE = "notification.cj.order.events.queue"
    NOTIFICATION_CJ_ORDER_EVENTS_DEAD_LETTER_QUEUE = "notification.cj.order.events.dlq"


class PaymentEventsQueue(StrEnum):
    PAYMENT_EVENTS_QUEUE = "payment.events.queue"
    PAYMENT_EVENTS_DEAD_LETTER_QUEUE = "payment.events.dlq"


class UserEvents(StrEnum):
    USER_REGISTERED = "user.registered"
    USER_EMAIL_VERIFIED = "user.email.verified"
    USER_LOGGED_IN = "user.logged.in"
    USER_PASSWORD_RESET_REQUEST = "user.password.reset.request"
    USER_PASSWORD_RESET_SUCCESS = "user.password.reset.success"


class OrderEvents(StrEnum):
    ORDER_CREATED = "order.created"
    ORDER_CONFIRMED = "order.confirmed"
    ORDER_CANCELLED = "order.cancelled"
    CJ_ORDER_CREATED = "cj.order.created"
    CJ_ORDER_FAILED = "cj.order.failed"
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
    # The authorized amount was captured: the customer is actually charged.
    PAYMENT_SUCCEEDED = "payment.succeeded"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"
    PAYMENT_CANCELLED = "payment.cancelled"
    # A customer disputed the charge with their bank (a chargeback).
    PAYMENT_DISPUTE_OPENED = "payment.dispute_opened"
    PAYMENT_DISPUTE_CLOSED = "payment.dispute_closed"


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


class ProductionEventsQueue(StrEnum):
    NOTIFICATION_PRODUCTION_EVENTS_QUEUE = "notification.production.events.queue"
    NOTIFICATION_PRODUCTION_EVENTS_DEAD_LETTER_QUEUE = "notification.production.events.dlq"
