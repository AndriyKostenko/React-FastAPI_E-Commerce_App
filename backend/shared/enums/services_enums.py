from enum import StrEnum


class Services(StrEnum):
    USER_SERVICE = "user-service"
    PRODUCT_SERVICE = "product-service"
    ORDER_SERVICE = "order-service"
    NOTIFICATION_SERVICE = "notification-service"