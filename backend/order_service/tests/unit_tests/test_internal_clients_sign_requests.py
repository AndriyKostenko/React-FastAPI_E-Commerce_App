"""
order-service's internal clients sign every request as order-service. Only the
network transport is replaced; the client, its auth and the key are real.
"""

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from pydantic import SecretStr

from service_layer.artwork_asset_client import ArtworkAssetClient
from service_layer.order_pricing_service import CatalogQuoteClient, FreightQuoteClient
from shared.auth.caller_assertion import CallerAssertionVerifier, RequestTarget
from shared.auth.service_assertion import SERVICE_ASSERTION_AUDIENCE, SERVICE_ASSERTION_HEADER
from shared.testing.signing_keys import EphemeralSigningKeys


KEYS = EphemeralSigningKeys()


def _settings() -> SimpleNamespace:
    pem = KEYS.order_service_private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()
    return SimpleNamespace(
        ORDER_SERVICE_ASSERTION_PRIVATE_KEY=SecretStr(pem),
        FULL_PRODUCT_SERVICE_URL="http://product-service:8002/api/v1",
        FULL_SUPPLIER_SERVICE_URL="http://supplier-service:8010/api/v1",
        CJ_DROPSHIPPING_FREIGHT_TIMEOUT_SECONDS=10,
    )


def _capture(body: dict[str, Any]) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handler), seen


def _verify(request: httpx.Request) -> None:
    verifier = CallerAssertionVerifier(
        KEYS.order_service_private_key.public_key(), "order-service", SERVICE_ASSERTION_AUDIENCE
    )
    verifier.verify(request.headers[SERVICE_ASSERTION_HEADER], RequestTarget(request.method, request.url.path))


@pytest.mark.parametrize(
    ("make_client", "call"),
    [
        (CatalogQuoteClient, lambda c: c.quote([])),
        (FreightQuoteClient, lambda c: c.quote("CA", "T1T 1T1", [])),
    ],
    ids=["catalog-quote", "freight-quote"],
)
async def test_quote_clients_sign_as_order_service(make_client: type, call: Callable) -> None:
    client = make_client(_settings())
    await client.start()
    transport, seen = _capture({"items": [], "options": []})
    client._client._transport = transport  # the network only
    try:
        await call(client)
    except Exception:
        # Only a failure *after* sending is acceptable: parsing the canned
        # response is not under test, the outgoing request is.
        if not seen:
            raise
    assert seen, "no request was sent"
    _verify(seen[0])  # raises if unsigned, forged, or bound to another path
    await client.close()


async def test_artwork_client_signs_as_order_service() -> None:
    client = ArtworkAssetClient(_settings())
    await client.start()
    transport, seen = _capture({})
    client._client._transport = transport
    asset = SimpleNamespace(model_dump=lambda mode: {"key": "artwork/x.png"}, key="artwork/x.png")
    try:
        await client.get_download(asset)
    except Exception:
        if not seen:
            raise
    _verify(seen[0])
    await client.close()
