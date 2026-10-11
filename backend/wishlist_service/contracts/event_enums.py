from enum import StrEnum


class WishlistEventsQueue(StrEnum):
    WISHLIST_EVENTS_QUEUE = "wishlist.events.queue"
    WISHLIST_EVENTS_DEAD_LETTER_QUEUE = "wishlist.events.dlq"


class UserEvents(StrEnum):
    USER_DELETED = "user.deleted"
