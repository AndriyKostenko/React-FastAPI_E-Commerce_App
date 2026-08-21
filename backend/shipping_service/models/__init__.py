"""Register every shipping-service model on the service-owned metadata."""

from .base import Base
from .shipping_models import Shipment, ShippingMethod
from .outbox_models import OutboxEvent

__all__ = ["Base", "Shipment", "ShippingMethod", "OutboxEvent"]
