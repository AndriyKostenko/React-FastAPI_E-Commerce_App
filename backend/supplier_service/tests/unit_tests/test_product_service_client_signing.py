"""
supplier-service asks product-service for the CJ products we sell, signed as
supplier-service. Only the network transport is replaced; the client, its
auth and the key are real.
"""

from types import SimpleNamespace

import httpx
import pytest
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from pydantic import SecretStr

from service_layer.product_service_client import ProductServiceClient, ProductServiceError
from shared.auth.caller_assertion import CallerAssertionVerifier, RequestTarget
from shared.auth.service_assertion import SERVICE_ASSERTION_AUDIENCE, SERVICE_ASSERTION_HEADER
from shared.testing.signing_keys import EphemeralSigningKeys

KEYS = EphemeralSigningKeys()


def _client(respond: httpx.Response) -> tuple[ProductServiceClient, list[httpx.Request]]:
    pem = KEYS.supplier_service_private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()
    settings = SimpleNamespace(
        SUPPLIER_SERVICE_ASSERTION_PRIVATE_KEY=SecretStr(pem),
        FULL_PRODUCT_SERVICE_URL="http://product-service:8002/api/v1",
    )
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return respond

    return ProductServiceClient(settings, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))), seen


async def test_the_stock_key_request_is_signed_as_supplier_service() -> None:
    client, seen = _client(httpx.Response(200, json=[{"supplier_pid": "P1", "vids": ["V1", "V2"]}]))

    keys = await client.list_stock_keys("cjdropshipping")

    assert [(k.supplier_pid, k.vids) for k in keys] == [("P1", ["V1", "V2"])]
    request = seen[0]
    assert request.url.path == "/api/v1/products/stock-keys/cjdropshipping"
    # Raises if unsigned, signed by another service, or bound to another path.
    CallerAssertionVerifier(
        KEYS.supplier_service_private_key.public_key(), "supplier-service", SERVICE_ASSERTION_AUDIENCE
    ).verify(request.headers[SERVICE_ASSERTION_HEADER], RequestTarget(request.method, request.url.path))


async def test_a_refused_request_is_an_error_not_an_empty_catalogue() -> None:
    """An empty list would look like "we sell nothing" and refresh nothing, silently."""
    client, _ = _client(httpx.Response(401, json={"detail": "Invalid service assertion"}))

    with pytest.raises(ProductServiceError, match="401"):
        await client.list_stock_keys("cjdropshipping")
