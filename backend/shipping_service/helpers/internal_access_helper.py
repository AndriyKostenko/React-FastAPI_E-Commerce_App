from ipaddress import ip_address, ip_network


class InternalAccessHelper:
    """Identifies internal paths and clients that bypass host validation."""

    INTERNAL_PATHS: set[str] = {"/health", "/metrics", "/docs", "/redoc", "/openapi.json"}
    INTERNAL_NETWORKS = [ip_network("10.0.0.0/8"), ip_network("172.16.0.0/12"), ip_network("192.168.0.0/16")]

    def is_internal_path(self, path: str) -> bool:
        """Check if the request path is an internal/health endpoint."""
        return path in self.INTERNAL_PATHS or path.startswith("/docs") or path.startswith("/openapi")

    def is_internal_client(self, request) -> bool:
        """Check if the request comes from a private/internal IP address."""
        client = request.client
        if not client or not client.host:
            return False
        try:
            addr = ip_address(client.host)
            return any(addr in network for network in self.INTERNAL_NETWORKS) or addr.is_loopback
        except ValueError:
            return False


internal_access_helper = InternalAccessHelper()
