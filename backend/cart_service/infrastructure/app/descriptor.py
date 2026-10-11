"""Identity of one ASGI service.

Every service repeated its title, description, version and port inline in its own
``main.py``, which is how ``order_service`` ended up serving user-service's
description from ``/docs``. A frozen value object gives each service exactly one
place to state who it is.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ServiceDescriptor:
    """The single source of truth for one service's identity and address."""

    name: str
    """Canonical slug — ``"user-service"``. Used as the telemetry and metrics label."""

    title: str
    description: str
    api_prefix: str
    host: str
    port: int
    version: str = "0.0.1"

    def openapi_kwargs(self) -> dict[str, str]:
        """The subset FastAPI's constructor takes for its OpenAPI header."""
        return {
            "title": self.title,
            "description": self.description,
            "version": self.version,
        }
