"""Unit tests for CJDropshippingAPIClient."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import HTTPStatusError, RequestError, Response

from exceptions.product_exceptions import CJDropshippingAPIError
from service_layer.cj_api_client import CJDropshippingAPIClient


@pytest.fixture
def client() -> CJDropshippingAPIClient:
    settings = SimpleNamespace(
        CJ_DROPSHIPPING_API_KEY="test-api-key",
        CJ_DROPSHIPPING_ACCESS_TOKEN_URL="https://developers.cjdropshipping.com/api2.0/v1/authentication/getAccessToken",
        CJ_DROPSHIPPING_AUTH_PAYLOAD={"apiKey": "test-api-key"},
    )
    return CJDropshippingAPIClient(settings=settings)  # type: ignore[arg-type]


class TestBuildUrl:
    def test_returns_base_url_without_params(self, client: CJDropshippingAPIClient) -> None:
        assert client.build_url("https://example.com/api") == "https://example.com/api"

    def test_appends_query_params(self, client: CJDropshippingAPIClient) -> None:
        url = client.build_url("https://example.com/api", {"page": 1, "keyWord": "phone"})
        assert url == "https://example.com/api?page=1&keyWord=phone"

    def test_skips_none_values(self, client: CJDropshippingAPIClient) -> None:
        url = client.build_url("https://example.com/api", {"pid": None, "page": 2})
        assert url == "https://example.com/api?page=2"


class TestAuthHeaders:
    def test_includes_content_type_only_when_no_token(self, client: CJDropshippingAPIClient) -> None:
        headers = client._auth_headers()
        assert headers == {"Content-Type": "application/json"}

    def test_includes_access_token_when_cached(self, client: CJDropshippingAPIClient) -> None:
        client._access_token = "cached-token"
        headers = client._auth_headers()
        assert headers["CJ-Access-Token"] == "cached-token"

    def test_uses_explicit_token_over_cached(self, client: CJDropshippingAPIClient) -> None:
        client._access_token = "cached-token"
        headers = client._auth_headers(access_token="explicit-token")
        assert headers["CJ-Access-Token"] == "explicit-token"


class TestGetAccessToken:
    async def test_stores_and_returns_token(self, client: CJDropshippingAPIClient) -> None:
        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {"data": {"accessToken": "cj-token-123"}}
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response):
            token = await client.get_access_token()

        assert token == "cj-token-123"
        assert client._access_token == "cj-token-123"

    async def test_raises_when_token_missing(self, client: CJDropshippingAPIClient) -> None:
        mock_response = MagicMock(spec=Response)
        mock_response.json.return_value = {"data": {}}
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(CJDropshippingAPIError):
                await client.get_access_token()

    async def test_ensure_access_token_returns_cached_token(self, client: CJDropshippingAPIClient) -> None:
        client._access_token = "already-cached"
        token = await client.ensure_access_token()
        assert token == "already-cached"


class TestErrorHandling:
    async def test_network_error_is_wrapped(self, client: CJDropshippingAPIClient) -> None:
        with patch("httpx.AsyncClient.request", new_callable=AsyncMock, side_effect=RequestError("timeout")):
            with pytest.raises(CJDropshippingAPIError, match="Network error"):
                await client.get_access_token()

    async def test_http_error_is_wrapped(self, client: CJDropshippingAPIClient) -> None:
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.json.return_value = {"message": "Invalid API key"}
        error = HTTPStatusError("Unauthorized", request=MagicMock(), response=mock_response)

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock, side_effect=error):
            with pytest.raises(CJDropshippingAPIError, match="401"):
                await client.get_access_token()
