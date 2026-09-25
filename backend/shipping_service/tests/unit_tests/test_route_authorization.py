"""
shipping-service enforces its own authorisation (bug list 4). A shipment holds
the buyer's address; reading one used to need only a signed-in user.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from shared.settings import get_test_settings
from shared.testing.authorization import Callers, RouteCase, assert_allowed, assert_denied
from tests.conftest import SIGNING_KEYS


SETTINGS = get_test_settings()
API = SETTINGS.API
CALLERS = Callers(SIGNING_KEYS)
OWNER, STRANGER = SETTINGS.TEST_USER_ID, uuid4()  # the mocked shipment belongs to TEST_USER_ID
METHOD = uuid4()

ADMIN_ONLY = [
    RouteCase("GET", f"{API}/shipping/methods/all"),
    RouteCase("POST", f"{API}/shipping/methods", json={}),
    RouteCase("PATCH", f"{API}/shipping/methods/{METHOD}", json={}),
    RouteCase("DELETE", f"{API}/shipping/methods/{METHOD}"),
    RouteCase("POST", f"{API}/shipments", json={}),
    RouteCase("PATCH", f"{API}/shipments/{SETTINGS.TEST_SHIPMENT_ID}", json={}),
]
OWNER_ONLY = [
    RouteCase("GET", f"{API}/shipments/{SETTINGS.TEST_SHIPMENT_ID}"),
    RouteCase("GET", f"{API}/shipments/order/{SETTINGS.TEST_ORDER_ID}"),
]


@pytest.mark.parametrize("case", ADMIN_ONLY + OWNER_ONLY, ids=str)
async def test_anonymous_is_refused(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_denied(client_for_unit_testing, case, CALLERS.anonymous, 401)


@pytest.mark.parametrize("case", ADMIN_ONLY, ids=str)
async def test_admin_route_refuses_a_user(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_denied(client_for_unit_testing, case, CALLERS.user(OWNER), 403)


@pytest.mark.parametrize("case", OWNER_ONLY, ids=str)
async def test_another_users_shipment_is_refused(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_denied(client_for_unit_testing, case, CALLERS.user(STRANGER), 403)


@pytest.mark.parametrize("case", OWNER_ONLY, ids=str)
async def test_owner_is_admitted(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_allowed(client_for_unit_testing, case, CALLERS.user(OWNER))


@pytest.mark.parametrize(
    "case",
    [RouteCase("GET", f"{API}/shipping/methods"), RouteCase("POST", f"{API}/shipping/rates", json={})],
    ids=str,
)
async def test_public_shipping_routes_stay_public(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_allowed(client_for_unit_testing, case, CALLERS.anonymous)
