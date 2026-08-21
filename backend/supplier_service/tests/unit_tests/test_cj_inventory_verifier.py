from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from service_layer.cj_api_client import CJDropshippingAPIError
from service_layer.cj_inventory_verifier import CJDropshippingInventoryVerifier


def _verifier(response):
    client = MagicMock()
    client.build_url.return_value = "https://cj.example/stock/queryByVid?vid=VID-1"
    client.request = AsyncMock(return_value=response)
    settings = SimpleNamespace(
        CJ_DROPSHIPPING_VERIFY_RETRIES=0,
        CJ_DROPSHIPPING_VERIFY_TIMEOUT_SECONDS=3,
        CJ_DROPSHIPPING_VARIANT_INVENTORY_URL=(
            "https://cj.example/stock/queryByVid"
        ),
        CJ_DROPSHIPPING_INVENTORY_BUFFER=2,
    )
    return CJDropshippingInventoryVerifier(client, settings), client


async def test_variant_stock_sums_warehouses_and_applies_buffer():
    verifier, client = _verifier(
        {
            "code": 200,
            "result": True,
            "data": [
                {"vid": "VID-1", "totalInventoryNum": 3},
                {"vid": "VID-1", "totalInventoryNum": 4},
            ],
        }
    )

    result = await verifier.verify_variant_stock("VID-1", 5)

    assert result.available == 7
    assert result.buffered_available == 5
    assert result.sufficient is True
    client.build_url.assert_called_once_with(
        "https://cj.example/stock/queryByVid", {"vid": "VID-1"}
    )


async def test_variant_stock_rejects_unsuccessful_response():
    verifier, _ = _verifier(
        {"code": 1600100, "result": False, "data": None}
    )

    with pytest.raises(CJDropshippingAPIError, match="vid=VID-1"):
        await verifier.verify_variant_stock("VID-1", 1)
