"""Unit tests for CJDropshippingProductProviderService."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from service_layer.cj_api_client import CJDropshippingAPIClient
from service_layer.dropshipping_provider import CJDropshippingProductProviderService
from shared.schemas.dropshipping_schemas import CJProductsFilterParams
from shared.utils.cj_filter_parser import CJFilterParser


@pytest.fixture
def provider() -> CJDropshippingProductProviderService:
    settings = SimpleNamespace(
        CJ_DROPSHIPPING_API_KEY="test-api-key",
        CJ_DROPSHIPPING_ACCESS_TOKEN_URL="https://developers.cjdropshipping.com/api2.0/v1/authentication/getAccessToken",
        CJ_DROPSHIPPING_PRODUCT_LIST_URL="https://developers.cjdropshipping.com/api2.0/v1/product/listV2",
        CJ_DROPSHIPPING_CATEGORY_LIST_URL="https://developers.cjdropshipping.com/api2.0/v1/product/getCategory",
        CJ_DROPSHIPPING_PRODUCT_INFO_URL="https://developers.cjdropshipping.com/api2.0/v1/product/query",
        CJ_DROPSHIPPING_BASE_URL="https://developers.cjdropshipping.com/api2.0/v1",
        CJ_DROPSHIPPING_AUTH_PAYLOAD={"apiKey": "test-api-key"},
    )
    return CJDropshippingProductProviderService(settings_instance=settings)  # type: ignore[arg-type]


class TestCJFilterParser:
    def test_parses_all_cj_filter_fields(self) -> None:
        filters = CJProductsFilterParams(
            page=2,
            size=50,
            keyWord="phone case",
            categoryId="123",
            countryCode="US",
            startSellPrice=Decimal("1.00"),
            endSellPrice=Decimal("10.00"),
            sort="desc",
            orderBy=1,
        )
        params = CJFilterParser.parse_filter_params(filters)

        assert params == {
            "page": 2,
            "size": 50,
            "keyWord": "phone case",
            "categoryId": "123",
            "countryCode": "US",
            "startSellPrice": Decimal("1.00"),
            "endSellPrice": Decimal("10.00"),
            "sort": "desc",
            "orderBy": 1,
        }

    def test_excludes_none_values(self) -> None:
        filters = CJProductsFilterParams(page=1, size=10)
        params = CJFilterParser.parse_filter_params(filters)

        assert params == {"page": 1, "size": 10}
        assert "keyWord" not in params
        assert "categoryId" not in params


class TestSearchProducts:
    async def test_uses_access_token_and_query_params(
        self, provider: CJDropshippingProductProviderService
    ) -> None:
        provider.api_client._access_token = "cached-token"
        response_data = {"data": {"productList": []}}

        filters = CJProductsFilterParams(keyWord="phone", page=1, size=10, categoryId="123")
        with patch.object(CJDropshippingAPIClient, "_request", new_callable=AsyncMock, return_value=response_data) as mock_request:
            result = await provider.search_products(filters_query=filters)

        assert result == response_data
        mock_request.assert_awaited_once()
        args, kwargs = mock_request.call_args
        assert args[0] == "GET"
        assert kwargs.get("params") is None
        url = args[1]
        assert "product/listV2" in url
        assert "keyWord=phone" in url
        assert "page=1" in url
        assert "size=10" in url
        assert "categoryId=123" in url


class TestGetProductDetails:
    async def test_fetches_by_pid(self, provider: CJDropshippingProductProviderService) -> None:
        provider.api_client._access_token = "cached-token"
        response_data = {"data": {"pid": "abc123"}}

        with patch.object(CJDropshippingAPIClient, "_request", new_callable=AsyncMock, return_value=response_data) as mock_request:
            result = await provider.get_product_details(pid="abc123")

        assert result == response_data
        args, kwargs = mock_request.call_args
        assert args[0] == "GET"
        assert "pid=abc123" in args[1]


class TestGetInventory:
    async def test_fetches_inventory_by_pid(self, provider: CJDropshippingProductProviderService) -> None:
        provider.api_client._access_token = "cached-token"
        response_data = {"data": {"inventories": []}}

        with patch.object(CJDropshippingAPIClient, "_request", new_callable=AsyncMock, return_value=response_data) as mock_request:
            result = await provider.get_inventory(pid="abc123")

        assert result == response_data
        args, kwargs = mock_request.call_args
        assert args[0] == "GET"
        assert "product/stock/getInventoryByPid" in args[1]
        assert "pid=abc123" in args[1]
