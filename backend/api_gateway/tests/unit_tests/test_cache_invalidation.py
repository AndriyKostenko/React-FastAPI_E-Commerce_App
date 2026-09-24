"""Which cache namespaces a mutation stales.

The mapping is ordered and anchored on path segments, and both properties are
load-bearing: a cart lives at /users/{id}/cart and a read-all at
/notifications/users/{id}, so an unanchored scan that reached "/users" first
would clear the wrong namespace and leave the real one serving stale data.
"""

import pytest

from shared.managers.cache_manager import CacheManager


@pytest.fixture
def cache_manager() -> CacheManager:
    # Only the pure mapping logic is under test; no Redis connection needed.
    return CacheManager.__new__(CacheManager)


class TestInvalidationNamespaces:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("/api/v1/products", ["products"]),
            ("/api/v1/products/abc", ["products"]),
            ("/api/v1/shipping/methods", ["shipping"]),
            ("/api/v1/users/abc", ["users"]),
        ],
    )
    def test_top_level_resources_map_to_their_own_namespace(
        self, cache_manager, path, expected
    ) -> None:
        assert cache_manager.get_invalidation_namespaces(path) == expected

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/users/abc/cart",
            "/api/v1/users/abc/cart/items",
            "/api/v1/users/abc/cart/items/xyz",
        ],
    )
    def test_a_cart_nested_under_users_stales_carts_not_users(
        self, cache_manager, path
    ) -> None:
        assert cache_manager.get_invalidation_namespaces(path) == ["carts"]

    def test_a_notification_read_all_nested_under_users_stales_notifications(
        self, cache_manager
    ) -> None:
        assert cache_manager.get_invalidation_namespaces(
            "/api/v1/notifications/users/abc/read-all"
        ) == ["notifications"]

    @pytest.mark.parametrize(
        "path", ["/api/v1/orders", "/api/v1/orders/abc/cancel", "/api/v1/shipments"]
    )
    def test_order_movement_also_stales_products(self, cache_manager, path) -> None:
        # Placing or cancelling an order reserves or releases stock, so cached
        # product listings showing availability are stale too.
        assert cache_manager.get_invalidation_namespaces(path) == ["orders", "products"]

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("/api/v1/categories", ["categories", "products"]),
            ("/api/v1/images", ["images", "products"]),
            ("/api/v1/reviews/product/abc", ["reviews", "products"]),
        ],
    )
    def test_embedded_data_changes_also_stale_products(
        self, cache_manager, path, expected
    ) -> None:
        assert cache_manager.get_invalidation_namespaces(path) == expected

    def test_an_unmapped_path_stales_nothing(self, cache_manager) -> None:
        assert cache_manager.get_invalidation_namespaces("/api/v1/unknown/thing") == []

    def test_every_mapped_namespace_is_a_known_namespace(self, cache_manager) -> None:
        """A namespace typo makes invalidate_namespace silently do nothing."""
        for _, namespaces in CacheManager._INVALIDATION_NAMESPACE_MAP:
            for namespace in namespaces:
                assert namespace in CacheManager.NAMESPACES, namespace
