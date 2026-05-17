"""Unit tests for ApiGateway: _prepare_headers and forward_request."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response as HttpxResponse

from gateway.apigateway import ApiGateway
from shared.shared_instances import settings, logger


def _make_gateway() -> ApiGateway:
    return ApiGateway(settings=settings, logger=logger)


class TestPrepareHeaders:
    def setup_method(self):
        self.gw = _make_gateway()

    def test_removes_hop_by_hop_headers(self):
        input_headers = {
            "host": "localhost:8000",
            "content-length": "42",
            "transfer-encoding": "chunked",
            "connection": "keep-alive",
            "content-type": "application/json",
            "authorization": "Bearer token",
        }
        result = self.gw._prepare_headers(input_headers)
        assert "host" not in result
        assert "content-length" not in result
        assert "transfer-encoding" not in result
        assert "connection" not in result
        assert "content-type" not in result
        assert "authorization" in result

    def test_adds_new_content_type(self):
        result = self.gw._prepare_headers({}, new_content_type="application/json")
        assert result["Content-Type"] == "application/json"

    def test_returns_empty_dict_for_empty_headers(self):
        result = self.gw._prepare_headers({})
        assert result == {}

    def test_keeps_custom_headers(self):
        result = self.gw._prepare_headers({"X-Custom-Header": "value123"})
        assert result["X-Custom-Header"] == "value123"

    def test_none_headers_returns_empty_dict(self):
        result = self.gw._prepare_headers(None)
        assert result == {}


class TestForwardRequest:
    def setup_method(self):
        self.gw = _make_gateway()

    def _make_mock_request(self, method: str = "GET", path: str = "/api/v1/products") -> MagicMock:
        req = MagicMock()
        req.method = method
        req.url = MagicMock()
        req.url.__str__ = MagicMock(return_value=f"http://localhost:8000{path}")
        req.headers = {}
        req.cookies = {}
        return req

    async def test_forward_get_returns_upstream_json(self):
        req = self._make_mock_request("GET", "/api/v1/products")

        mock_response = MagicMock(spec=HttpxResponse)
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_response.headers = {}

        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(return_value=mock_response)

        with patch.object(ApiGateway, "_http_client", mock_http_client):
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

        with patch.object(ApiGateway, "_http_client", mock_http_client):
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
        with patch.object(ApiGateway, "_http_client", mock_http_client):
            result = await self.gw.forward_request(
                request=req,
                service_name="order-service",
                override_body=override,
            )

        assert result.status_code == 201
        call_kwargs = mock_http_client.request.call_args.kwargs
        assert call_kwargs["json"] == override
