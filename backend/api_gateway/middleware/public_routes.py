from dataclasses import dataclass
from enum import Enum


class PathScope(Enum):
    """Which request paths a public route declaration covers."""

    # Only the path itself: "/login" matches "/login" and nothing else.
    EXACT = "exact"
    # The path and every path below it: "/products" matches "/products" and
    # "/products/<id>/reviews", but never the sibling "/products-export".
    TREE = "tree"
    # Only paths below it: "/images/generations" matches
    # "/images/generations/<job>/status" but not "/images/generations".
    CHILDREN = "children"


@dataclass(frozen=True, slots=True)
class PublicRoute:
    """One path (and optionally methods) reachable without authentication."""

    path: str
    methods: frozenset[str] | None = None  # None means every method
    scope: PathScope = PathScope.EXACT
    # The gateway caches a GET response and replays it to every caller, so
    # only routes whose answer is identical for everyone may opt in. Public
    # is not enough: a public route can still personalise its response.
    cacheable: bool = False

    def matches(self, path: str, method: str) -> bool:
        if self.methods is not None and method not in self.methods:
            return False
        base = self.path.rstrip("/") or "/"
        is_self = path == base or path == f"{base}/"
        # Children are matched on a segment boundary, so the base must be
        # followed by "/" — a bare startswith() would also open up siblings
        # that merely share the prefix.
        is_child = path.startswith(f"{base}/") and len(path) > len(base) + 1
        match self.scope:
            case PathScope.EXACT:
                return is_self
            case PathScope.TREE:
                return is_self or is_child
            case PathScope.CHILDREN:
                return is_child


class PublicRouteRegistry:
    """The allowlist of routes the gateway serves without a valid session."""

    def __init__(
        self,
        routes: tuple[PublicRoute, ...],
        protected: tuple[PublicRoute, ...] = (),
    ) -> None:
        self._routes = routes
        # Carve-outs from a public TREE. They must be excluded here, not just
        # guarded in the route: public GETs are cached by the gateway for every
        # caller, so an admin's response would be replayed to anonymous users.
        self._protected = protected

    def is_public(self, path: str, method: str) -> bool:
        if self._is_protected(path, method):
            return False
        return any(route.matches(path, method) for route in self._routes)

    def is_cacheable(self, path: str, method: str) -> bool:
        """Whether a response may be served from the shared, caller-blind cache."""
        if self._is_protected(path, method):
            return False
        return any(route.cacheable and route.matches(path, method) for route in self._routes)

    def _is_protected(self, path: str, method: str) -> bool:
        return any(route.matches(path, method) for route in self._protected)

    @classmethod
    def for_api_version(cls, api: str) -> "PublicRouteRegistry":
        get, post = frozenset({"GET"}), frozenset({"POST"})
        return cls((
            # Infrastructure
            PublicRoute("/health", scope=PathScope.TREE),
            PublicRoute("/metrics", scope=PathScope.TREE),
            PublicRoute("/media", scope=PathScope.TREE),
            PublicRoute("/docs", scope=PathScope.TREE),
            PublicRoute("/redoc", scope=PathScope.TREE),
            PublicRoute("/openapi.json"),
            # Auth flows — the token (if any) travels in the body, so these are
            # exact paths with nothing below them.
            PublicRoute(f"{api}/register", post),
            PublicRoute(f"{api}/login", post),
            PublicRoute(f"{api}/google-login", post),
            PublicRoute(f"{api}/refresh", post),
            PublicRoute(f"{api}/logout", post),
            PublicRoute(f"{api}/forgot-password", post),
            PublicRoute(f"{api}/activate", post),
            PublicRoute(f"{api}/password-reset", post),
            # Catalogue browsing
            PublicRoute(f"{api}/products", get, PathScope.TREE, cacheable=True),
            PublicRoute(f"{api}/categories", get, PathScope.TREE, cacheable=True),
            PublicRoute(f"{api}/customization/pricing", get, cacheable=True),
            # Stripe authenticates itself with the webhook signature
            PublicRoute(f"{api}/payments/webhook", post),
            # Shipping lookups at checkout
            PublicRoute(f"{api}/shipping/methods", get, PathScope.TREE, cacheable=True),
            PublicRoute(f"{api}/shipping/rates", post),
        ), protected=(
            # Admin-only, including inactive methods
            PublicRoute(f"{api}/shipping/methods/all", get),
        ))
