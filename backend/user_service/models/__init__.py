"""Register every user-service model on the service-owned metadata."""

from .base import Base
from .address_models import UserAddress
from .outbox_models import OutboxEvent
from .user_models import User
from .webauthn_credential_models import WebAuthnCredential

__all__ = ["Base", "OutboxEvent", "User", "UserAddress", "WebAuthnCredential"]
