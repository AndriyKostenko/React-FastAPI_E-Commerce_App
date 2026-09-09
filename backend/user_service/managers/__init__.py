"""Process-scoped resource graphs owned by user-service."""

from managers.outbox_manager import OutboxManager, UserOutboxResources
from managers.resources_manager import (
    SERVICE_NAME,
    ResourceManager,
    UserApiResources,
    logger,
    rate_limited,
    settings,
)

__all__ = [
    "SERVICE_NAME",
    "OutboxManager",
    "ResourceManager",
    "UserApiResources",
    "UserOutboxResources",
    "logger",
    "rate_limited",
    "settings",
]
