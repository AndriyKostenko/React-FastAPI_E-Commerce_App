"""
What the gateway refuses or neutralises from a request before trusting it:
paths it would forward somewhere else, metrics labels a caller could invent,
cache keys two different queries could share, a caller-chosen request id, and
the CJ catalogue routes, which are not for customers.
"""
from logging import getLogger
from unittest.mock import AsyncMock, patch
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from starlette.datastructures import Headers

from app_config import UNMATCHED_ROUTE_LABEL, route_label
from infrastructure.managers.cache_manager import CacheManager
from infrastructure.middleware.logging_middleware import _request_id_from
from main import app
from middleware.path_guard import RequestPathGuard
from tests.constants import TEST_API, TEST_PRODUCT_ID


class TestRequestPathGuard:
    """Paths whose forwarded form would differ from the one the gateway judged."""

    def test_why_it_exists_httpx_collapses_dot_segments_upstream(self) -> None:
        # The gateway matches "/products/../orders" (a public catalogue path)
        # but httpx sends "/orders": the guard closes that gap at the edge.
        assert httpx.URL("http://product-service/api/v1/products/../orders").path == "/api/v1/orders"

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/products/../orders",
            "/api/v1/products/./cards",
            "/media/../api/v1/products",
            "/api/v1/wishlists/me/items/..",
            "/api/v1/products/a\\..\\orders",
            "/api/v1/orders/x?admin=1",  # a decoded %3F
            "/api/v1/orders/x#y",  # a decoded %23
            "/api/v1/orders/%2e%2e",  # a decoded %252e: decoded again upstream
            "/api/v1/orders/x\x00",
            "/api/v1/orders/x\r\nX-Injected: 1",
        ],
    )
    def test_refuses(self, path: str) -> None:
        assert RequestPathGuard.is_safe(path) is False

    @pytest.mark.parametrize(
        "path",
        [
            "/",
            "/health",
            "/docs",
            "/openapi.json",
            f"/api/v1/products/{TEST_PRODUCT_ID}/detailed",
            "/api/v1/cjdropshipping/products/04A22450-67F0-4617-A132-E7AE7F8963B0",
            "/media/generated-designs/0f3c9a.png",
            "/api/v1/images/generations/job_1.v2~a/status",
        ],
    )
    def test_lets_every_route_shape_through(self, path: str) -> None:
        assert RequestPathGuard.is_safe(path) is True

    @pytest.mark.parametrize(
        "raw_path",
        [
            f"{TEST_API}/products/%2e%2e/orders",
            f"{TEST_API}/products/{TEST_PRODUCT_ID}%2F..%2F..%2Forders",
            f"{TEST_API}/orders/{TEST_PRODUCT_ID}%3Fuser_id%3Dx",
        ],
    )
    async def test_the_app_answers_400_and_forwards_nothing(
        self, client: AsyncClient, mock_forward: AsyncMock, raw_path: str
    ) -> None:
        # Percent-encoded, as a client would have to send it: httpx (like a
        # browser) resolves a literal "..", and the server decodes these.
        response = await client.get(raw_path)
        assert response.status_code == 400, response.text
        assert response.json() == {"detail": "Invalid request path"}
        mock_forward.assert_not_awaited()

    async def test_media_traversal_never_reaches_product_service(self, client: AsyncClient) -> None:
        upstream = AsyncMock()
        with patch.object(app.state.resources.gateway, "_http_client", upstream):
            response = await client.get("/media/%2e%2e/api/v1/admin/orders")
        assert response.status_code == 400
        upstream.get.assert_not_called()


class TestMetricsRouteLabel:
    """The gateway's request metrics are labelled by route template, never by raw path."""

    @pytest.fixture
    def labels(self) -> list[str]:
        return []

    @pytest.fixture
    def probe_app(self, labels: list[str]) -> FastAPI:
        # The gateway reads the label after call_next in an http middleware,
        # exactly as here; the router must have recorded the matched route by then.
        probe = FastAPI()

        @probe.middleware("http")
        async def record(request: Request, call_next):
            response = await call_next(request)
            labels.append(route_label(request))
            return response

        @probe.get("/api/v1/products/{product_id}")
        async def product(product_id: UUID) -> dict[str, str]:
            return {"id": str(product_id)}

        return probe

    async def test_ids_share_their_route_template(self, probe_app: FastAPI, labels: list[str]) -> None:
        async with AsyncClient(transport=ASGITransport(app=probe_app), base_url="http://test") as http:
            for product_id in ("7b0e1c1e-6a4a-4f0e-9a43-6a1f3c0b1a01", "1d4bf3c8-0a83-49b5-8b7e-2b3a5c0f9e02"):
                assert (await http.get(f"/api/v1/products/{product_id}")).status_code == 200
        assert labels == ["/api/v1/products/{product_id}"] * 2

    async def test_a_response_answered_before_routing_keeps_its_template(self, labels: list[str]) -> None:
        # A cache hit is returned by the gateway's middleware, so the router never
        # records a route; the label must still be the template, not "unmatched".
        probe = FastAPI()

        @probe.middleware("http")
        async def answer_from_cache(request: Request, call_next):
            labels.append(route_label(request))
            return JSONResponse({"cached": True})

        @probe.get("/api/v1/products/{product_id}")
        async def product(product_id: UUID) -> dict[str, str]:
            raise AssertionError("a cached response never reaches the route")

        async with AsyncClient(transport=ASGITransport(app=probe), base_url="http://test") as http:
            await http.get("/api/v1/products/7b0e1c1e-6a4a-4f0e-9a43-6a1f3c0b1a01")
        assert labels == ["/api/v1/products/{product_id}"]

    async def test_made_up_paths_share_one_label(self, probe_app: FastAPI, labels: list[str]) -> None:
        async with AsyncClient(transport=ASGITransport(app=probe_app), base_url="http://test") as http:
            for junk in ("/wp-login.php", "/a/b/c", "/api/v1/nothing-here"):
                assert (await http.get(junk)).status_code == 404
        assert labels == [UNMATCHED_ROUTE_LABEL] * 3


class TestCacheKey:
    """Two queries the service answers differently never share a cached response."""

    @pytest.fixture
    def cache(self) -> CacheManager:
        # The connection is lazy: key generation never touches Redis.
        return CacheManager(
            service_prefix="api-gateway",
            redis_url="redis://127.0.0.1:6379/0",
            logger=getLogger("test"),
            service_api_version="/api/v1",
        )

    @staticmethod
    def _request(query_string: bytes) -> Request:
        return Request({
            "type": "http", "method": "GET", "path": "/api/v1/products", "query_string": query_string,
            "headers": [], "scheme": "http", "server": ("testserver", 80), "root_path": "",
        })

    def test_an_encoded_ampersand_is_not_a_second_parameter(self, cache: CacheManager) -> None:
        one_parameter = self._request(b"search_term=shirt%26sort_by%3Dprice")
        two_parameters = self._request(b"search_term=shirt&sort_by=price")
        assert cache._generate_cache_key(one_parameter) != cache._generate_cache_key(two_parameters)

    def test_every_value_of_a_repeated_parameter_counts(self, cache: CacheManager) -> None:
        both = self._request(b"ids=a&ids=b")
        last_only = self._request(b"ids=b")
        assert cache._generate_cache_key(both) != cache._generate_cache_key(last_only)

    def test_parameter_order_still_does_not_matter(self, cache: CacheManager) -> None:
        assert cache._generate_cache_key(self._request(b"limit=20&offset=40")) == cache._generate_cache_key(
            self._request(b"offset=40&limit=20")
        )


class TestRequestId:
    """An incoming X-Request-ID is kept only when it looks like one."""

    @staticmethod
    def _request(value: str | None) -> Request:
        headers = Headers({"X-Request-ID": value} if value is not None else {})
        return Request({"type": "http", "headers": headers.raw})

    @pytest.mark.parametrize("value", ["3f1c2b9e-1d2a-4b8e-9c3f-0a1b2c3d4e5f", "trace.abc_123-XYZ"])
    def test_a_well_formed_id_is_kept(self, value: str) -> None:
        assert _request_id_from(self._request(value)) == value

    @pytest.mark.parametrize("value", [None, "", "x" * 129, "id with spaces", '"},{"level":"critical', "é"])
    def test_anything_else_is_replaced_with_a_fresh_uuid(self, value: str | None) -> None:
        assigned = _request_id_from(self._request(value))
        assert assigned != value
        assert UUID(assigned)

    async def test_the_response_echoes_the_replacement(self, client: AsyncClient) -> None:
        response = await client.get(f"{TEST_API}/products", headers={"X-Request-ID": "x" * 500})
        assert response.status_code == 200
        assert UUID(response.headers["X-Request-ID"])


class TestCjCatalogueRoutes:
    """CJ search and raw product details carry our cost and spend the shared CJ budget."""

    @pytest.mark.parametrize("path", ["/cjdropshipping/products", "/cjdropshipping/products/1424608189734850560"])
    async def test_a_customer_is_refused(self, client: AsyncClient, mock_forward: AsyncMock, path: str) -> None:
        response = await client.get(f"{TEST_API}{path}")
        assert response.status_code == 403
        mock_forward.assert_not_awaited()

    @pytest.mark.parametrize("path", ["/cjdropshipping/products", "/cjdropshipping/products/1424608189734850560"])
    async def test_an_admin_is_forwarded(self, admin_client: AsyncClient, mock_forward: AsyncMock, path: str) -> None:
        response = await admin_client.get(f"{TEST_API}{path}")
        assert response.status_code == 200
        mock_forward.assert_awaited_once()
