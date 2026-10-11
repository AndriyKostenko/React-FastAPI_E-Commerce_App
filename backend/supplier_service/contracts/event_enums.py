from enum import StrEnum


class ProductSupplierEventsQueue(StrEnum):
    # Separate queue for supplier_service to receive import-feedback events.
    # Using a distinct queue name prevents supplier_service and product_service
    # from competing on the same physical RabbitMQ queue (shared-queue collision).
    SUPPLIER_FEEDBACK_EVENTS_QUEUE = "supplier.feedback.events"
    SUPPLIER_FEEDBACK_EVENTS_DLQ = "supplier.feedback.events.dlq"


class InventoryEvents(StrEnum):
    INVENTORY_RELEASE_REQUESTED = "inventory.release.requested"


class OrderEvents(StrEnum):
    ORDER_CONFIRMED = "order.confirmed"
    ORDER_CANCELLED = "order.cancelled"
    CJ_ORDER_CREATED = "cj.order.created"
    CJ_ORDER_FAILED = "cj.order.failed"
    # CJ accepted and was paid for the order from our balance: the goods are
    # committed, so the customer's authorized card can now be captured.
    CJ_ORDER_PAID = "cj.order.paid"
    CJ_ORDER_SHIPPED = "cj.order.shipped"
    CJ_ORDER_DELIVERED = "cj.order.delivered"


class SupplierEvents(StrEnum):
    SUPPLIER_PRODUCTS_FETCHED = "supplier.products.fetched"
    SUPPLIER_PRODUCT_IMPORT_COMPLETED = "supplier.product.import.completed"
    SUPPLIER_PRODUCT_IMPORT_FAILED = "supplier.product.import.failed"
    # The hourly refresh of CJ's US-warehouse stock for the products we sell.
    SUPPLIER_STOCK_UPDATED = "supplier.stock.updated"
