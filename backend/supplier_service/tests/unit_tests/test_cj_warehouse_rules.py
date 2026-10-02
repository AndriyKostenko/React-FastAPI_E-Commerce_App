"""
China warehouses only: what reaches CJ when products are listed, and which stock counts.

Only the HTTP call to CJ is replaced; the request parameters and the parsing
of CJ's documented inventory responses are the real code.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlparse

import pytest

from schemas.dropshipping_schemas import CJProductsFilterParams
from service_layer.cj_api_client import CJDropshippingAPIClient
from service_layer.cj_inventory_verifier import CJDropshippingInventoryVerifier
from service_layer.cj_product_provider import CJDropshippingProductProvider

LIST_URL = "https://cj.example/product/listV2"
PID_STOCK_URL = "https://cj.example/product/stock/getInventoryByPid"
VID_STOCK_URL = "https://cj.example/product/stock/queryByVid"

_SETTINGS = SimpleNamespace(
    CJ_DROPSHIPPING_PRODUCT_LIST_URL=LIST_URL,
    CJ_DROPSHIPPING_INVENTORY_URL=PID_STOCK_URL,
    CJ_DROPSHIPPING_VARIANT_INVENTORY_URL=VID_STOCK_URL,
    CJ_DROPSHIPPING_VERIFY_RETRIES=0,
    CJ_DROPSHIPPING_VERIFY_TIMEOUT_SECONDS=3,
    CJ_DROPSHIPPING_INVENTORY_BUFFER=0,
)


def _client(response: dict[str, object]) -> MagicMock:
    client = MagicMock()
    # The real URL builder, so the query string sent to CJ is what is checked.
    client.build_url.side_effect = CJDropshippingAPIClient.build_url
    client.ensure_access_token = AsyncMock(return_value="token")
    client.request = AsyncMock(return_value=response)
    return client


# ---------------------------------------------------------------- listing


@pytest.mark.parametrize("asked_for", [None, "US", "GB"])
async def test_every_product_search_asks_cj_for_china_warehouse_stock(asked_for: str | None) -> None:
    client = _client({"code": 200, "result": True, "data": {"content": []}})
    provider = CJDropshippingProductProvider(_SETTINGS, api_client=client)

    await provider.search_products(CJProductsFilterParams(countryCode=asked_for))

    url = client.request.await_args.args[1]
    assert parse_qs(urlparse(url).query)["countryCode"] == ["CN"]


# ------------------------------------------------------------ order stock


def _vid_stock(*rows: tuple[str, int]) -> dict[str, object]:
    """CJ's documented stock/queryByVid response: one row per warehouse."""
    return {
        "code": 200,
        "result": True,
        "data": [
            {"vid": "VID-1", "areaEn": f"{code} Warehouse", "countryCode": code, "totalInventoryNum": qty}
            for code, qty in rows
        ],
    }


async def test_us_stock_never_covers_an_order() -> None:
    # CJ cannot ship from the US to Canada, so stock there is no use.
    verifier = CJDropshippingInventoryVerifier(_client(_vid_stock(("US", 10000), ("CN", 2))), _SETTINGS)

    result = await verifier.verify_variant_stock("VID-1", 3)

    assert (result.available, result.sufficient, result.warehouses_checked) == (2, False, 1)


async def test_china_stock_covers_an_order() -> None:
    verifier = CJDropshippingInventoryVerifier(_client(_vid_stock(("US", 0), ("CN", 4), ("cn", 1))), _SETTINGS)

    result = await verifier.verify_variant_stock("VID-1", 5)

    assert (result.available, result.sufficient) == (5, True)


async def test_product_stock_counts_only_the_china_warehouse() -> None:
    verifier = CJDropshippingInventoryVerifier(
        _client({
            "code": 200,
            "result": True,
            "data": {"inventories": [
                {"countryCode": "US", "totalInventoryNum": 900},
                {"countryCode": "CN", "totalInventoryNum": 30},
            ]},
        }),
        _SETTINGS,
    )

    result = await verifier.verify_product_stock("PID-1", 31)

    assert (result.available, result.sufficient) == (30, False)


# -------------------------------------------------------- catalogue stock


async def test_catalogue_stock_reads_china_rows_per_product_and_per_variant() -> None:
    """CJ's documented getInventoryByPid shape: variant rows under "inventory"."""
    client = _client({
        "code": 200,
        "result": True,
        "data": {
            "inventories": [
                {"countryCode": "US", "totalInventoryNum": 10044},
                {"countryCode": "CN", "areaEn": "China Warehouse", "totalInventoryNum": 264},
            ],
            "variantInventories": [
                {"vid": "V-S", "inventory": [
                    {"countryCode": "US", "totalInventory": 5000},
                    {"countryCode": "CN", "totalInventory": 200},
                ]},
                {"vid": "V-M", "inventory": [{"countryCode": "CN", "totalInventory": 64}]},
                {"vid": "V-XL", "inventory": [{"countryCode": "US", "totalInventory": 5044}]},
            ],
        },
    })
    verifier = CJDropshippingInventoryVerifier(client, _SETTINGS)

    stock = await verifier.fetch_warehouse_stock("PID-1")

    assert stock.total == 264
    assert stock.by_vid == {"V-S": 200, "V-M": 64, "V-XL": 0}
    assert parse_qs(urlparse(client.request.await_args.args[1]).query) == {"pid": ["PID-1"]}
