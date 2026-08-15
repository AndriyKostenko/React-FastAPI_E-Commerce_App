"""Register every order-service model on the service-owned metadata."""

from .base import Base
from .order_address_models import OrderAddress
from .order_item_models import OrderItem
from .order_models import Order
from .outbox_models import OutboxEvent

__all__ = ["Base", "Order", "OrderAddress", "OrderItem", "OutboxEvent"]
