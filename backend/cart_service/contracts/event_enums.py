from enum import StrEnum


class CartEventsQueue(StrEnum):
    CART_ORDER_EVENTS_QUEUE = "cart.order.events.queue"
    CART_ORDER_EVENTS_DEAD_LETTER_QUEUE = "cart.order.events.dlq"


class OrderEvents(StrEnum):
    ORDER_CREATED = "order.created"
    ORDER_CONFIRMED = "order.confirmed"
