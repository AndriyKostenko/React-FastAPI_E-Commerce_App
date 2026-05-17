"""Unit tests for GatewayCachePolicy — pure-logic TTL and namespace resolution."""
import pytest

from gateway.cache_policy import GatewayCachePolicy


@pytest.fixture
def policy() -> GatewayCachePolicy:
    return GatewayCachePolicy()


class TestGetInvalidationNamespace:
    def test_products_returns_products(self, policy: GatewayCachePolicy):
        assert policy.get_invalidation_namespace("/api/v1/products") == "products"

    def test_products_detailed_returns_products(self, policy: GatewayCachePolicy):
        assert policy.get_invalidation_namespace("/api/v1/products/detailed") == "products"

    def test_categories_returns_categories(self, policy: GatewayCachePolicy):
        assert policy.get_invalidation_namespace("/api/v1/categories") == "categories"

    def test_images_returns_images(self, policy: GatewayCachePolicy):
        assert policy.get_invalidation_namespace("/api/v1/images") == "images"

    def test_reviews_returns_reviews(self, policy: GatewayCachePolicy):
        assert policy.get_invalidation_namespace("/api/v1/reviews") == "reviews"

    def test_orders_returns_orders(self, policy: GatewayCachePolicy):
        assert policy.get_invalidation_namespace("/api/v1/orders") == "orders"

    def test_users_returns_users(self, policy: GatewayCachePolicy):
        assert policy.get_invalidation_namespace("/api/v1/users") == "users"

    def test_notifications_returns_notifications(self, policy: GatewayCachePolicy):
        assert policy.get_invalidation_namespace("/api/v1/notifications") == "notifications"

    def test_unknown_path_returns_none(self, policy: GatewayCachePolicy):
        assert policy.get_invalidation_namespace("/api/v1/payments") is None

    def test_case_insensitive(self, policy: GatewayCachePolicy):
        assert policy.get_invalidation_namespace("/api/v1/PRODUCTS") == "products"


class TestGetCacheTtl:
    def test_products_ttl(self, policy: GatewayCachePolicy):
        assert policy.get_cache_ttl("/api/v1/products") == 300

    def test_products_detailed_ttl(self, policy: GatewayCachePolicy):
        assert policy.get_cache_ttl("/api/v1/products/detailed") == 600

    def test_categories_ttl(self, policy: GatewayCachePolicy):
        assert policy.get_cache_ttl("/api/v1/categories") == 300

    def test_images_ttl(self, policy: GatewayCachePolicy):
        assert policy.get_cache_ttl("/api/v1/images") == 300

    def test_reviews_ttl(self, policy: GatewayCachePolicy):
        assert policy.get_cache_ttl("/api/v1/reviews") == 300

    def test_unknown_path_returns_default(self, policy: GatewayCachePolicy):
        assert policy.get_cache_ttl("/api/v1/orders") == GatewayCachePolicy.DEFAULT_TTL

    def test_default_ttl_is_300(self, policy: GatewayCachePolicy):
        assert GatewayCachePolicy.DEFAULT_TTL == 300
