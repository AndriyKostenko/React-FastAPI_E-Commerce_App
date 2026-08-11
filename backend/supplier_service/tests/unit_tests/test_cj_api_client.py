"""Unit tests for CJDropshippingAPIClient."""
from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import HTTPStatusError, Request

from service_layer.cj_api_client import CJDropshippingAPIClient
from shared.settings import Settings


@pytest.fixture
def settings() -> Settings:
    s = Settings()
    s.CJ_DROPSHIPPING_ACCESS_TOKEN_URL = "https://api.cjdropshipping.com/authentication/getAccessToken"
    s.CJ_DROPSHIPPING_PRODUCT_LIST_URL = "https://api.cjdropshipping.com/product/listV2"
    s.CJ_DROPSHIPPING_API_KEY = "testkey"
    s.CJ_DROPSHIPPING_REQUEST_TIMEOUT_SECONDS = 5.0
    return s


@pytest.mark.asyncio
async def test_get_access_token(settings: Settings) -> None:
    client = CJDropshippingAPIClient(settings)
    mock_http = AsyncMock()
    mock_http.request.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": True, "data": {"accessToken": "token_123"}},
    )
    client._http_client = mock_http

    token = await client.get_access_token()
    assert token == "token_123"
    assert client._access_token == "token_123"


@pytest.mark.asyncio
async def test_ensure_access_token_uses_cache_or_fetches(settings: Settings) -> None:
    client = CJDropshippingAPIClient(settings)
    client._access_token = "cached_token"
    client.get_access_token = AsyncMock(return_value="new_token")

    # When not forced, returns cached token
    token = await client.ensure_access_token(force_refresh=False)
    assert token == "cached_token"
    client.get_access_token.assert_not_called()

    # When forced, fetches new token
    token = await client.ensure_access_token(force_refresh=True)
    client.get_access_token.assert_called_once()


@pytest.mark.asyncio
async def test_request_auto_refreshes_on_401(settings: Settings) -> None:
    client = CJDropshippingAPIClient(settings)
    client._access_token = "old_token"

    response_401 = MagicMock()
    response_401.status_code = 401
    response_401.text = "Unauthorized"
    response_401.raise_for_status.side_effect = HTTPStatusError(
        "Unauthorized", request=Request("GET", settings.CJ_DROPSHIPPING_PRODUCT_LIST_URL), response=response_401
    )

    response_200 = MagicMock()
    response_200.status_code = 200
    response_200.json.return_value = {"data": "success"}

    mock_http = AsyncMock()
    mock_http.request.side_effect = [response_401, response_200]
    client._http_client = mock_http

    client.ensure_access_token = AsyncMock(return_value="new_refreshed_token")

    result = await client.request("GET", settings.CJ_DROPSHIPPING_PRODUCT_LIST_URL)

    assert result == {"data": "success"}
    client.ensure_access_token.assert_called_with(force_refresh=True)
