"""Unit tests for ApiGateway: _prepare_headers and forward_request."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response as HttpxResponse

from starlette.requests import Request

from uuid import uuid4
from urllib.parse import urlparse

from gateway.apigateway import ApiGateway
from resources import logger, settings
from shared.auth.caller_assertion import CALLER_ASSERTION_HEADER, RequestTarget
from shared.contracts.auth import TokenClaims
from shared.testing.signing_keys import EphemeralSigningKeys


KEYS = EphemeralSigningKeys()


def _make_gateway() -> ApiGateway:
    return ApiGateway(settings=settings, logger=logger, assertion_signer=KEYS.assertion_signer())


def _make_request(headers: dict[str, str] | None = None, peer: str = "203.0.113.9") -> Request:
    """Build a real Request so header and client-address handling is exercised."""
    return Request({
        "type": "http",
        "method": "GET",
        "scheme": "http",
        "path": "/api/v1/products",
        "raw_path": b"/api/v1/products",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (key.lower().encode(), value.encode())
            for key, value in (headers or {}).items()
        ],
        "client": (peer, 51234),
        "server": ("localhost", 8000),
    })


class TestPrepareHeaders:
    def setup_method(self):
        self.gw = _make_gateway()

    def test_removes_hop_by_hop_headers(self):
        request = _make_request({
            "host": "localhost:8000",
            "content-length": "42",
            "transfer-encoding": "chunked",
            "connection": "keep-alive",
            "content-type": "application/json",
            "authorization": "Bearer token",
        })
        result = self.gw._prepare_headers(request)
        assert "host" not in result
        assert "content-length" not in result
        assert "transfer-encoding" not in result
        assert "connection" not in result
        assert "content-type" not in result

    def test_strips_the_callers_credentials_and_any_identity_it_claims(self):
        # The session token and cookies stop at the gateway; a client-made
        # assertion or a retired identity header must never reach a service.
        request = _make_request({
            "authorization": "Bearer token",
            "cookie": "access_token=abc; refresh_token=def",
            CALLER_ASSERTION_HEADER: "forged",
            "X-Authenticated-User-Id": str(uuid4()),
            "X-Authenticated-User-Role": "admin",
        })
        forwarded = {name.lower() for name in self.gw._prepare_headers(request)}
        assert forwarded.isdisjoint({
            "authorization",
            "cookie",
            CALLER_ASSERTION_HEADER.lower(),
            "x-authenticated-user-id",
            "x-authenticated-user-role",
        })

    def test_adds_new_content_type(self):
        result = self.gw._prepare_headers(_make_request(), new_content_type="application/json")
        assert result["Content-Type"] == "application/json"

    def test_forwards_only_derived_headers_when_none_supplied(self):
        result = self.gw._prepare_headers(_make_request())
        assert set(result) == {
            "X-Forwarded-For",
            "X-Real-Ip",
            "X-Forwarded-Proto",
            "X-Forwarded-Host",
        }

    def test_keeps_custom_headers(self):
        result = self.gw._prepare_headers(_make_request({"X-Custom-Header": "value123"}))
        # Starlette normalises incoming header names to lower case.
        assert result["x-custom-header"] == "value123"

    def test_discards_forwarding_headers_from_an_untrusted_peer(self):
        """A direct caller must not be able to choose its own attributed address."""
        request = _make_request(
            {"x-forwarded-for": "1.2.3.4", "x-real-ip": "1.2.3.4", "forwarded": "for=1.2.3.4"},
            peer="203.0.113.9",
        )
        result = self.gw._prepare_headers(request)
        assert result["X-Forwarded-For"] == "203.0.113.9"
        assert result["X-Real-Ip"] == "203.0.113.9"
        assert "forwarded" not in {key.lower() for key in result}

    def test_takes_the_rightmost_untrusted_hop_from_a_trusted_proxy(self):
        """Traefik appends the real peer, so spoofed entries sit to its left."""
        request = _make_request(
            {"x-forwarded-for": "1.2.3.4, 198.51.100.7"},
            peer="172.20.0.4",
        )
        result = self.gw._prepare_headers(request)
        assert result["X-Forwarded-For"] == "198.51.100.7"


class TestForwardRequest:
    def setup_method(self):
        self.gw = _make_gateway()

    def _make_mock_request(self, method: str = "GET", path: str = "/api/v1/products") -> MagicMock:
        req = MagicMock()
        req.method = method
        req.url = MagicMock()
        req.url.__str__ = MagicMock(return_value=f"http://localhost:8000{path}")
        req.url.scheme = "http"
        req.url.hostname = "localhost"
        req.url.netloc = "localhost:8000"
        req.headers = {}
        req.cookies = {}
        req.client = MagicMock()
        req.client.host = "172.20.0.4"
        req.state = MagicMock(current_user=None)
        return req

    async def test_forward_attaches_an_assertion_the_service_can_verify(self):
        req = self._make_mock_request("DELETE", "/api/v1/products/abc")
        user_id = uuid4()
        req.state.current_user = TokenClaims(email="admin@example.com", id=user_id, role="admin")

        mock_response = MagicMock(spec=HttpxResponse)
        mock_response.status_code = 204
        mock_response.headers = {}
        mock_response.content = b""
        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(return_value=mock_response)

        with patch.object(self.gw, "_http_client", mock_http_client):
            await self.gw.forward_request(request=req, service_name="product-service")

        sent = mock_http_client.request.call_args.kwargs
        # Verified exactly as product-service would: for the downstream method and path.
        caller = KEYS.assertion_verifier().verify(
            sent["headers"][CALLER_ASSERTION_HEADER],
            RequestTarget(method=sent["method"], path=urlparse(sent["url"]).path),
        )
        assert caller.user_id == user_id
        assert caller.role == "admin"

    async def test_forward_get_returns_upstream_json(self):
        req = self._make_mock_request("GET", "/api/v1/products")

        mock_response = MagicMock(spec=HttpxResponse)
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_response.headers = {}

        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(return_value=mock_response)

        with patch.object(self.gw, "_http_client", mock_http_client):
            result = await self.gw.forward_request(request=req, service_name="product-service")

        assert result.status_code == 200

    async def test_forward_unknown_service_raises_404(self):
        from fastapi import HTTPException
        req = self._make_mock_request("GET", "/api/v1/unknown")

        with pytest.raises(HTTPException) as exc_info:
            await self.gw.forward_request(request=req, service_name="nonexistent-service")

        assert exc_info.value.status_code == 404

    async def test_forward_request_error_raises_500(self):
        from httpx import RequestError
        from fastapi import HTTPException

        req = self._make_mock_request("GET", "/api/v1/products")

        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(side_effect=RequestError("connection refused"))

        with patch.object(self.gw, "_http_client", mock_http_client):
            with pytest.raises(HTTPException) as exc_info:
                await self.gw.forward_request(request=req, service_name="product-service")

        assert exc_info.value.status_code == 500

    async def test_forward_with_override_body_sends_json(self):
        req = self._make_mock_request("POST", "/api/v1/orders")

        mock_response = MagicMock(spec=HttpxResponse)
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "order-123"}
        mock_response.headers = {}

        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(return_value=mock_response)

        override = {"user_id": "abc", "total": 50}
        with patch.object(self.gw, "_http_client", mock_http_client):
            result = await self.gw.forward_request(
                request=req,
                service_name="order-service",
                override_body=override,
            )

        assert result.status_code == 201
        call_kwargs = mock_http_client.request.call_args.kwargs
        assert call_kwargs["json"] == override

    async def test_image_generation_path_uses_standard_timeout(self):
        # Image-generation POST now returns 202 immediately; the background task
        # handles long-running work, so the gateway uses the standard timeout.
        req = self._make_mock_request("POST", "/api/v1/images/generations")
        req.headers = {"content-type": "application/json"}
        req.json = AsyncMock(return_value={"prompt": "test prompt", "style": "Streetwear"})

        mock_response = MagicMock(spec=HttpxResponse)
        mock_response.status_code = 201
        mock_response.json.return_value = {"image_url": "/media/generated/test.png"}
        mock_response.headers = {}

        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(return_value=mock_response)

        with patch.object(self.gw, "_http_client", mock_http_client):
            await self.gw.forward_request(request=req, service_name="product-service")

        call_kwargs = mock_http_client.request.call_args.kwargs
        assert call_kwargs["timeout"] == self.gw._TIMEOUT

    async def test_regular_product_path_uses_default_timeout(self):
        req = self._make_mock_request("GET", "/api/v1/products")

        mock_response = MagicMock(spec=HttpxResponse)
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_response.headers = {}

        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(return_value=mock_response)

        with patch.object(self.gw, "_http_client", mock_http_client):
            await self.gw.forward_request(request=req, service_name="product-service")

        call_kwargs = mock_http_client.request.call_args.kwargs
        assert call_kwargs["timeout"] == self.gw._TIMEOUT


class TestServiceRegistry:
    def test_every_known_service_is_routable(self):
        # cart-service was missing, so every cart route answered 404
        # "Service not found" while the service itself was healthy.
        from shared.enums.services_enums import Services

        assert set(Services) <= set(_make_gateway().config.services)

    def test_cart_url_resolves_to_the_cart_service(self):
        gateway = _make_gateway()
        url = gateway.url_manager.build_url("cart-service", "/users/abc/cart")
        assert url.startswith(settings.FULL_CART_SERVICE_URL)
