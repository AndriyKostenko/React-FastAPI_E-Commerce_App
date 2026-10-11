from enum import StrEnum


class ShippingEventsQueue(StrEnum):
    SHIPPING_EVENTS_QUEUE = "shipping.events.queue"
    SHIPPING_EVENTS_DEAD_LETTER_QUEUE = "shipping.events.dlq"


class OrderEvents(StrEnum):
    ORDER_CONFIRMED = "order.confirmed"
    ORDER_CANCELLED = "order.cancelled"


class ShippingEvents(StrEnum):
    SHIPMENT_CREATED = "shipment.created"
    SHIPMENT_SHIPPED = "shipment.shipped"
    SHIPMENT_DELIVERED = "shipment.delivered"
    SHIPMENT_CANCELLED = "shipment.cancelled"
