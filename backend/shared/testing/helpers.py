"""Test helpers that avoid duplication across service conftest files."""

from shared.settings import get_settings


def allow_testserver_host() -> None:
    """
    Ensure the default ASGI test-client host ('testserver') passes the
    host-validation middleware used by every service.

    This mutates the cached settings object in place; the change only affects
    the current test process.
    """
    settings = get_settings()
    if "testserver" not in settings.ALLOWED_HOSTS:
        settings.ALLOWED_HOSTS.append("testserver")
