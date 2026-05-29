class GatewayCachePolicy:
    """
    Encapsulates all gateway-level cache configuration:
    - which URL path segments map to Redis invalidation namespaces (supports multi-namespace)
    - per-path TTLs for GET response caching
    """

    # Ordered most-specific → least-specific so the first match wins.
    # Values are lists to allow a single mutation to invalidate multiple namespaces.
    # e.g. updating a category also stales cached product-detail responses that embed category data.
    _INVALIDATION_NAMESPACE_MAP: list[tuple[str, list[str]]] = [
        ("products/detailed", ["products"]),
        ("/products", ["products"]),
        ("/categories", ["categories", "products"]),   # category change → stale embedded product data
        ("/images", ["images", "products"]),            # image change → stale embedded product data
        ("/reviews", ["reviews", "products"]),          # review change → stale embedded product data
        ("/orders", ["orders"]),
        ("/users", ["users"]),
        ("/notifications", ["notifications"]),
    ]

    _CACHE_TTL_MAP: list[tuple[str, int]] = [
        ("/products/detailed", 600),
        ("/products", 300),
        ("/categories", 300),
        ("/images", 300),
        ("/reviews", 300),
    ]

    DEFAULT_TTL: int = 300

    def get_invalidation_namespaces(self, path: str) -> list[str]:
        """Return all cache namespaces to invalidate after a successful mutation on *path*."""
        path_lower = path.lower()
        for segment, namespaces in self._INVALIDATION_NAMESPACE_MAP:
            if segment in path_lower:
                return namespaces
        return []

    def get_cache_ttl(self, path: str) -> int:
        """Return the TTL (seconds) to use when caching a GET response for *path*."""
        path_lower = path.lower()
        for segment, ttl in self._CACHE_TTL_MAP:
            if segment in path_lower:
                return ttl
        return self.DEFAULT_TTL


cache_policy = GatewayCachePolicy()
