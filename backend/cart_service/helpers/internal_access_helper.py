from fastapi import Request


class InternalAccessHelper:
    """Encapsulates internal monitoring path and network checks."""
    def __init__(self) -> None:
        self._internal_paths = frozenset({"/metrics", "/health"})
        self._private_prefixes = ("10.", "172.", "192.168.")

    def is_internal_path(self, path: str) -> bool:
        return path in self._internal_paths

    def is_internal_client(self, request: Request) -> bool:
        client_host = request.client.host if request.client else ""
        return self.is_internal_path(request.url.path) or any(
            client_host.startswith(prefix) for prefix in self._private_prefixes
        )


internal_access_helper = InternalAccessHelper()
