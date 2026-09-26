"""
The two routes order-service calls directly accept order-service's signature
and nothing else — not an anonymous caller, not even a signed-in admin.
"""

import pytest
from httpx import AsyncClient

from shared.testing.signing_keys import ANONYMOUS, EphemeralSigningKeys
from tests.conftest import DEFAULT_CALLER, SIGNING_KEYS, TEST_API


INTERNAL_ROUTES = [f"{TEST_API}/products/order-quote", f"{TEST_API}/artwork/download-link"]


@pytest.mark.parametrize("path", INTERNAL_ROUTES)
@pytest.mark.parametrize(
    ("caller", "why"),
    [
        (ANONYMOUS, "anyone who reaches the service directly"),
        (DEFAULT_CALLER, "a user, even an admin, through the gateway"),
        (EphemeralSigningKeys().order_service_auth(), "someone without order-service's key"),
    ],
    ids=["anonymous", "admin-user", "forged-key"],
)
async def test_only_order_service_may_call(client_for_unit_testing: AsyncClient, path: str, caller, why: str) -> None:
    response = await client_for_unit_testing.post(path, json={}, auth=caller)
    assert response.status_code == 401, why


@pytest.mark.parametrize("path", INTERNAL_ROUTES)
async def test_order_service_gets_past_the_guard(client_for_unit_testing: AsyncClient, path: str) -> None:
    response = await client_for_unit_testing.post(path, json={}, auth=SIGNING_KEYS.order_service_auth())
    # Past authentication; the empty body is then rejected by validation.
    assert response.status_code not in (401, 403)
