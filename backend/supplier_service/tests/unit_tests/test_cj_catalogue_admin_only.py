"""
CJ catalogue search and raw product details are for admins only: the results
carry CJ's price (our cost), and each call spends the CJ budget checkout's
freight quotes share. The guard is the real one, fed by real gateway
assertions (EphemeralSigningKeys); a refused caller never reaches CJ.
"""

from collections.abc import AsyncGenerator
from logging import getLogger
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from infrastructure.middleware.caller_assertion_middleware import CallerAssertionMiddleware
from infrastructure.testing.signing_keys import ANONYMOUS, EphemeralSigningKeys
from routes.supplier_routes import supplier_routes

KEYS = EphemeralSigningKeys()
CJ_PATHS = ("/api/v1/cjdropshipping/products", "/api/v1/cjdropshipping/products/1424608189734850560")


@pytest.fixture
async def customer_client() -> AsyncGenerator[AsyncClient, None]:
    app = FastAPI()
    app.add_middleware(CallerAssertionMiddleware, logger=getLogger("test"))
    app.include_router(supplier_routes, prefix="/api/v1")
    KEYS.install_verifier(app)
    customer = KEYS.caller_auth(user_id=uuid4(), role="user")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=customer) as http:
        yield http


@pytest.mark.parametrize("path", CJ_PATHS)
async def test_a_customer_is_refused(customer_client: AsyncClient, path: str) -> None:
    response = await customer_client.get(path)
    assert response.status_code == 403, response.text


@pytest.mark.parametrize("path", CJ_PATHS)
async def test_an_anonymous_caller_is_refused(customer_client: AsyncClient, path: str) -> None:
    response = await customer_client.get(path, auth=ANONYMOUS)
    assert response.status_code in (401, 403), response.text
