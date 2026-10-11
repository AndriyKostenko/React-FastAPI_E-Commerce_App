from enum import StrEnum


class ProductInventoryEventsQueue(StrEnum):
    PRODUCT_INVENTORY_EVENTS_QUEUE = "product.inventory.events"
    PRODUCT_INVENTORY_EVENTS_DEAD_LETTER_QUEUE = "product.inventory.events.dlq"


class ProductSupplierEventsQueue(StrEnum):
    PRODUCT_SUPPLIER_EVENTS_QUEUE = "product.supplier.events"
    PRODUCT_SUPPLIER_EVENTS_DEAD_LETTER_QUEUE = "product.supplier.events.dlq"
    # Stock refreshes get their own queue: a long import batch never delays one.
    PRODUCT_SUPPLIER_STOCK_QUEUE = "product.supplier.stock"
    PRODUCT_SUPPLIER_STOCK_DLQ = "product.supplier.stock.dlq"


class InventoryEvents(StrEnum):
    INVENTORY_RESERVE_SUCCEEDED = "inventory.reserve.succeeded"
    INVENTORY_RESERVE_FAILED = "inventory.reserve.failed"
    INVENTORY_RESERVE_REQUESTED = "inventory.reserve.requested"
    INVENTORY_RELEASE_REQUESTED = "inventory.release.requested"


class SupplierEvents(StrEnum):
    SUPPLIER_PRODUCTS_FETCHED = "supplier.products.fetched"
    SUPPLIER_PRODUCT_IMPORT_COMPLETED = "supplier.product.import.completed"
    SUPPLIER_PRODUCT_IMPORT_FAILED = "supplier.product.import.failed"
    # The hourly refresh of CJ's US-warehouse stock for the products we sell.
    SUPPLIER_STOCK_UPDATED = "supplier.stock.updated"


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
