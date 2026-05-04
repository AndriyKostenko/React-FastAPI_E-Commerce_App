from enum import StrEnum


class UserEventsQueue(StrEnum):
    USER_EVENTS_QUEUE = "user.events.queue"
    USER_EVENTS_DEAD_LETTER_QUEUE = "user.events.dlq"


class OrderEventsQueue(StrEnum):
    ORDER_EVENTS_QUEUE = "order.events.queue"
    ORDER_EVENTS_DEAD_LETTER_QUEUE = "order.events.dlq"


class OrderSagaResponseQueue(StrEnum):
    ORDER_SAGA_RESPONSE_QUEUE = "order.saga.response"
    ORDER_SAGA_RESPONSE_DEAD_LETTER_QUEUE = "order.saga.response.dlq"


class ProductInventoryEventsQueue(StrEnum):
    PRODUCT_INVENTORY_EVENTS_QUEUE = "product.inventory.events"
    PRODUCT_INVENTORY_EVENTS_DEAD_LETTER_QUEUE = "product.inventory.events.dlq"


class ProductEventsQueue(StrEnum):
    PRODUCT_EVENTS_QUEUE = "product.events.queue"
    PRODUCT_EVENTS_DEAD_LETTER_QUEUE = "product.events.dlq"


class UserEvents(StrEnum):
    USER_REGISTERED = "user.registered"
    USER_REGISTRATION_FAILED = "user.registration.failed"
    USER_EMAIL_VERIFICATION_REQUEST = "user.email.verification.request"
    USER_EMAIL_VERIFIED = "user.email.verified"
    USER_LOGGED_IN = "user.logged.in"
    USER_PASSWORD_RESET_REQUEST = "user.password.reset.request"
    USER_PASSWORD_RESET_SUCCESS = "user.password.reset.success"


class InventoryEvents(StrEnum):
    INVENTORY_RESERVE_SUCCEEDED = "inventory.reserve.succeeded"
    INVENTORY_RESERVE_FAILED = "inventory.reserve.failed"
    INVENTORY_RELEASED = "inventory.released"
    INVENTORY_RESERVE_REQUESTED = "inventory.reserve.requested"
    INVENTORY_RELEASE_REQUESTED = "inventory.release.requested"


class OrderEvents(StrEnum):
    ORDER_CREATED = "order.created"
    ORDER_CONFIRMED = "order.confirmed"
    ORDER_CANCELLED = "order.cancelled"


class PaymentEvents(StrEnum):
    PAYMENT_SUCCEEDED = "payment.succeeded"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"
