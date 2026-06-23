from enum import StrEnum


class Services(StrEnum):
    USER_SERVICE = "user-service"
    PRODUCT_SERVICE = "product-service"
    ORDER_SERVICE = "order-service"
    NOTIFICATION_SERVICE = "notification-service"
    PAYMENT_SERVICE = "payment-service"
    CART_SERVICE = "cart-service"
    SHIPPING_SERVICE = "shipping-service"
    WISHLIST_SERVICE = "wishlist-service"
