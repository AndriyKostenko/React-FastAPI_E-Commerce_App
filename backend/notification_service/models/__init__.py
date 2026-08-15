"""Register every notification-service model on the service-owned metadata."""

from .base import Base
from .notification_models import Notification

__all__ = ["Base", "Notification"]
