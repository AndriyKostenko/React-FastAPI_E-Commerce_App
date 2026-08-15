"""Register every user-service model on the service-owned metadata."""

from .base import Base
from .outbox_models import OutboxEvent
from .user_models import User

__all__ = ["Base", "OutboxEvent", "User"]
