"""Unit tests for UrlManager — pure-logic path extraction and URL building."""
from logging import getLogger
from unittest.mock import MagicMock

import pytest

from gateway.apigateway import UrlManager
from shared.schemas.gateway_schemas import GatewayConfig, ServiceConfig


def _make_url_manager(instances: list[str] | None = None) -> UrlManager:
    instances = instances or ["http://user-service:8001"]
    config = GatewayConfig(
        services={
            "user-service": ServiceConfig(
                name="user-service",
                instances=instances,
                health_check_path="/health",
                api_version="/api/v1",
            ),
            "product-service": ServiceConfig(
                name="product-service",
                instances=["http://product-service:8002"],
                health_check_path="/health",
                api_version="/api/v1",
            ),
        }
    )
    return UrlManager(config=config, logger=MagicMock())


class TestExtractServicePath:
    def test_strips_api_version_prefix(self):
        um = _make_url_manager()
        result = um.extract_service_path("http://127.0.0.1:8000/api/v1/login", "user-service")
        assert result == "/login"

    def test_strips_api_version_with_nested_path(self):
        um = _make_url_manager()
        result = um.extract_service_path("http://127.0.0.1:8000/api/v1/users/abc", "user-service")
        assert result == "/users/abc"

    def test_preserves_query_string(self):
        um = _make_url_manager()
        result = um.extract_service_path(
            "http://127.0.0.1:8000/api/v1/users?limit=10&offset=0", "user-service"
        )
        assert result == "/users?limit=10&offset=0"

    def test_path_without_api_version_prefix(self):
        um = _make_url_manager()
        result = um.extract_service_path("http://127.0.0.1:8000/login", "user-service")
        assert result.startswith("/")

    def test_returns_root_for_version_only(self):
        um = _make_url_manager()
        result = um.extract_service_path("http://127.0.0.1:8000/api/v1", "user-service")
        assert result == "/"


class TestBuildUrl:
    def test_builds_correct_url_with_single_instance(self):
        um = _make_url_manager(instances=["http://user-service:8001"])
        url = um.build_url("user-service", "/login")
        assert url == "http://user-service:8001/api/v1/login"

    def test_builds_url_with_query_string(self):
        um = _make_url_manager(instances=["http://user-service:8001"])
        url = um.build_url("user-service", "/users?limit=5")
        assert "limit=5" in url
        assert url.startswith("http://user-service:8001")

    def test_builds_url_for_product_service(self):
        um = _make_url_manager()
        url = um.build_url("product-service", "/products")
        assert url == "http://product-service:8002/api/v1/products"

    def test_multiple_instances_always_picks_one(self):
        instances = ["http://user-service-1:8001", "http://user-service-2:8001"]
        um = _make_url_manager(instances=instances)
        url = um.build_url("user-service", "/login")
        assert url.startswith("http://user-service-1:8001") or url.startswith("http://user-service-2:8001")
