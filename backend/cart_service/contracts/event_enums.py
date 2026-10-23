from enum import StrEnum


class CartEventsQueue(StrEnum):
    CART_ORDER_EVENTS_QUEUE = "cart.order.events.queue"
    CART_ORDER_EVENTS_DEAD_LETTER_QUEUE = "cart.order.events.dlq"
    # user.deleted: the deleted customer's cart goes too.
    CART_USER_EVENTS_QUEUE = "cart.user.events.queue"
    CART_USER_EVENTS_DEAD_LETTER_QUEUE = "cart.user.events.dlq"


class UserEvents(StrEnum):
    USER_DELETED = "user.deleted"


class OrderEvents(StrEnum):
    ORDER_CREATED = "order.created"
    ORDER_CONFIRMED = "order.confirmed"
