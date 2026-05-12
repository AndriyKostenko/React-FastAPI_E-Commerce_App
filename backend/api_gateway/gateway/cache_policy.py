class GatewayCachePolicy:
    """
    Encapsulates all gateway-level cache configuration:
    - which URL path segments map to a Redis invalidation namespace
    - per-path TTLs for GET response caching
    """

    # Ordered most-specific → least-specific so the first match wins.
    _INVALIDATION_NAMESPACE_MAP: list[tuple[str, str]] = [
        ("products/detailed", "products"),
        ("/products", "products"),
        ("/categories", "categories"),
        ("/images", "images"),
        ("/reviews", "reviews"),
        ("/orders", "orders"),
        ("/users", "users"),
        ("/notifications", "notifications"),
    ]

    _CACHE_TTL_MAP: list[tuple[str, int]] = [
        ("/products/detailed", 600),
        ("/products", 300),
        ("/categories", 300),
        ("/images", 300),
        ("/reviews", 300),
    ]

    DEFAULT_TTL: int = 300

    def get_invalidation_namespace(self, path: str) -> str | None:
        """Return the cache namespace to invalidate after a successful mutation on *path*."""
        path_lower = path.lower()
        for segment, namespace in self._INVALIDATION_NAMESPACE_MAP:
            if segment in path_lower:
                return namespace
        return None

    def get_cache_ttl(self, path: str) -> int:
        """Return the TTL (seconds) to use when caching a GET response for *path*."""
        path_lower = path.lower()
        for segment, ttl in self._CACHE_TTL_MAP:
            if segment in path_lower:
                return ttl
        return self.DEFAULT_TTL


cache_policy = GatewayCachePolicy()
