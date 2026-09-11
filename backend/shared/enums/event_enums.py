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


class OrderSagaResponseQueue(StrEnum):
    ORDER_SAGA_RESPONSE_QUEUE = "order.saga.response"
    ORDER_SAGA_RESPONSE_DEAD_LETTER_QUEUE = "order.saga.response.dlq"


class ProductInventoryEventsQueue(StrEnum):
    PRODUCT_INVENTORY_EVENTS_QUEUE = "product.inventory.events"
    PRODUCT_INVENTORY_EVENTS_DEAD_LETTER_QUEUE = "product.inventory.events.dlq"


class ProductEventsQueue(StrEnum):
    PRODUCT_EVENTS_QUEUE = "product.events.queue"
    PRODUCT_EVENTS_DEAD_LETTER_QUEUE = "product.events.dlq"


class CartEventsQueue(StrEnum):
    CART_ORDER_EVENTS_QUEUE = "cart.order.events.queue"
    CART_ORDER_EVENTS_DEAD_LETTER_QUEUE = "cart.order.events.dlq"


class ShippingEventsQueue(StrEnum):
    SHIPPING_EVENTS_QUEUE = "shipping.events.queue"
    SHIPPING_EVENTS_DEAD_LETTER_QUEUE = "shipping.events.dlq"


class WishlistEventsQueue(StrEnum):
    WISHLIST_EVENTS_QUEUE = "wishlist.events.queue"
    WISHLIST_EVENTS_DEAD_LETTER_QUEUE = "wishlist.events.dlq"


class SupplierEventsQueue(StrEnum):
    SUPPLIER_EVENTS_QUEUE = "supplier.events.queue"
    SUPPLIER_EVENTS_DEAD_LETTER_QUEUE = "supplier.events.dlq"


class ProductSupplierEventsQueue(StrEnum):
    PRODUCT_SUPPLIER_EVENTS_QUEUE = "product.supplier.events"
    PRODUCT_SUPPLIER_EVENTS_DEAD_LETTER_QUEUE = "product.supplier.events.dlq"
    # Separate queue for supplier_service to receive import-feedback events.
    # Using a distinct queue name prevents supplier_service and product_service
    # from competing on the same physical RabbitMQ queue (shared-queue collision).
    SUPPLIER_FEEDBACK_EVENTS_QUEUE = "supplier.feedback.events"
    SUPPLIER_FEEDBACK_EVENTS_DLQ = "supplier.feedback.events.dlq"


class UserEvents(StrEnum):
    USER_REGISTERED = "user.registered"
    USER_REGISTRATION_FAILED = "user.registration.failed"
    USER_EMAIL_VERIFICATION_REQUEST = "user.email.verification.request"
    USER_EMAIL_VERIFIED = "user.email.verified"
    USER_LOGGED_IN = "user.logged.in"
    USER_PASSWORD_RESET_REQUEST = "user.password.reset.request"
    USER_PASSWORD_RESET_SUCCESS = "user.password.reset.success"
    USER_DELETED = "user.deleted"


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
    CJ_ORDER_CREATED = "cj.order.created"
    CJ_ORDER_FAILED = "cj.order.failed"
    # CJ accepted and was paid for the order from our balance: the goods are
    # committed, so the customer's authorized card can now be captured.
    CJ_ORDER_PAID = "cj.order.paid"
    CJ_ORDER_SHIPPED = "cj.order.shipped"
    CJ_ORDER_DELIVERED = "cj.order.delivered"


class PaymentEvents(StrEnum):
    # The card is authorized (funds held, not yet charged).
    PAYMENT_AUTHORIZED = "payment.authorized"
    # The authorized amount was captured: the customer is actually charged.
    PAYMENT_SUCCEEDED = "payment.succeeded"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"
    PAYMENT_CANCELLED = "payment.cancelled"


class PaymentCommands(StrEnum):
    """Instructions order_service sends payment_service about a held card.

    They travel on the order exchange under "payment.*.requested" keys, which
    match none of the "order.#", "order.*", "cj.order.*" or "production.job.#"
    bindings there, so only payment_service's own queue receives them.
    """

    CAPTURE_REQUESTED = "payment.capture.requested"
    RELEASE_REQUESTED = "payment.release.requested"


class ShippingEvents(StrEnum):
    SHIPMENT_CREATED = "shipment.created"
    SHIPMENT_SHIPPED = "shipment.shipped"
    SHIPMENT_DELIVERED = "shipment.delivered"
    SHIPMENT_CANCELLED = "shipment.cancelled"


class WishlistEvents(StrEnum):
    WISHLIST_ITEM_ADDED = "wishlist.item.added"
    WISHLIST_ITEM_REMOVED = "wishlist.item.removed"


class SupplierEvents(StrEnum):
    SUPPLIER_PRODUCTS_FETCHED = "supplier.products.fetched"
    SUPPLIER_PRODUCT_IMPORT_COMPLETED = "supplier.product.import.completed"
    SUPPLIER_PRODUCT_IMPORT_FAILED = "supplier.product.import.failed"


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


class ArtworkEvents(StrEnum):
    """Retention markers linking a paid order line to its stored print file.

    product_service owns the artwork object but order_service owns the
    reference, so these events are what let a cleanup job tell a paid order's
    print file from an abandoned generation draft.
    """

    ARTWORK_RETAINED = "artwork.retained"
    ARTWORK_RELEASED = "artwork.released"


class ProductArtworkEventsQueue(StrEnum):
    PRODUCT_ARTWORK_EVENTS_QUEUE = "product.artwork.events.queue"
    PRODUCT_ARTWORK_EVENTS_DEAD_LETTER_QUEUE = "product.artwork.events.dlq"
