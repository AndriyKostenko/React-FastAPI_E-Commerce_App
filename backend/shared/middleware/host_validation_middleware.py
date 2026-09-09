"""Strict Host-header validation shared by every service."""

from collections.abc import Iterable
from logging import Logger

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.utils.client_ip import ClientIPResolver


class HostValidator:
    """Decides whether a request's Host header names this deployment.

    A Host header the application echoes back — in a redirect, a password-reset
    link, a cached response key — is attacker-controlled unless it is checked,
    which is what makes DNS rebinding and cache-poisoning practical. So the
    rule is an allowlist rather than a bypass.

    Two lists feed it. ``ALLOWED_HOSTS`` is the public names the deployment
    answers to. ``INTERNAL_ALLOWED_HOSTS`` is the container DNS names services
    use to reach each other: a gateway calling ``http://user-service:8001``
    legitimately sends ``Host: user-service``, and that must be accepted
    without falling back to "trust any Host from a private IP", which would
    accept every Host header an attacker inside the network cared to send.

    Both lists are read per request rather than snapshotted, because the
    settings object is a process-wide singleton that tests mutate in place
    after the middleware has already been constructed.
    """

    def __init__(self, settings) -> None:
        self._settings = settings

    def _allowed_hosts(self) -> set[str]:
        public = getattr(self._settings, "ALLOWED_HOSTS", ()) or ()
        internal = getattr(self._settings, "INTERNAL_ALLOWED_HOSTS", ()) or ()
        return {host.strip().lower() for host in (*public, *internal) if host}

    def is_allowed(self, hostname: str | None) -> bool:
        allowed = self._allowed_hosts()
        # A wildcard is honoured because operators set it deliberately in
        # development; it is never the default.
        if "*" in allowed:
            return True
        if not hostname:
            return False
        return hostname.lower() in allowed


def add_host_validation_middleware(
    app: FastAPI,
    *,
    settings,
    logger: Logger,
    exempt_paths: Iterable[str] = ("/health", "/metrics"),
) -> None:
    """Reject any request whose Host header this deployment does not answer to.

    ``/health`` and ``/metrics`` are exempt: Docker health checks and Prometheus
    address containers by IP or short name and have no meaningful Host, and
    neither endpoint reflects the header or exposes user data.
    """
    validator = HostValidator(settings)
    resolver = ClientIPResolver(settings.TRUSTED_PROXY_NETWORKS)
    exempt = frozenset(exempt_paths)

    @app.middleware("http")
    async def host_validation_middleware(request: Request, call_next):
        if request.url.path in exempt:
            return await call_next(request)

        if validator.is_allowed(request.url.hostname):
            return await call_next(request)

        logger.warning(
            "Invalid Host header: %s from %s",
            request.url.hostname or "<missing>",
            resolver.resolve(request),
        )
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid Host header"},
            headers={"X-Error": "Invalid Host header"},
        )
