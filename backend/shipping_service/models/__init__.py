"""Register every shipping-service model on the service-owned metadata."""

from .base import Base
from .shipping_models import Shipment, ShippingMethod

__all__ = ["Base", "Shipment", "ShippingMethod"]
