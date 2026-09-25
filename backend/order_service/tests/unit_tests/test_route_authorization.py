"""
order-service enforces its own authorisation (bug list 4), whatever the gateway
did or did not check. Callers are real signed assertions, not overrides.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from shared.testing.authorization import Callers, RouteCase, assert_allowed, assert_denied
from tests.conftest import SIGNING_KEYS
from tests.constants import TEST_API, TEST_ORDER_ID, TEST_USER_ID
from tests.unit_tests.test_order_routes import _order_payload


CALLERS = Callers(SIGNING_KEYS)
OWNER = TEST_USER_ID  # the user_id of the order the mocked service returns
STRANGER = uuid4()

ADMIN_ONLY = [
    RouteCase("GET", f"{TEST_API}/orders"),
    RouteCase("PATCH", f"{TEST_API}/orders/{TEST_ORDER_ID}", json={"status": "confirmed"}),
    RouteCase("DELETE", f"{TEST_API}/orders/{TEST_ORDER_ID}"),
    RouteCase("GET", f"{TEST_API}/admin/schema/orders"),
    RouteCase("GET", f"{TEST_API}/admin/production/jobs"),
    RouteCase("GET", f"{TEST_API}/admin/production/jobs/{uuid4()}"),
    RouteCase("POST", f"{TEST_API}/admin/production/jobs/{uuid4()}/start", json={}),
]
SIGNED_IN = [
    RouteCase("POST", f"{TEST_API}/orders/quote", json={}),
    RouteCase("POST", f"{TEST_API}/orders", json=_order_payload()),
    RouteCase("GET", f"{TEST_API}/orders/{TEST_ORDER_ID}"),
    RouteCase("PATCH", f"{TEST_API}/orders/{TEST_ORDER_ID}/cancel", json={"reason": "changed my mind"}),
    RouteCase("GET", f"{TEST_API}/orders/user/{OWNER}"),
]


@pytest.mark.parametrize("case", ADMIN_ONLY + SIGNED_IN, ids=str)
async def test_anonymous_is_refused(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_denied(client_for_unit_testing, case, CALLERS.anonymous, 401)


@pytest.mark.parametrize("case", ADMIN_ONLY, ids=str)
async def test_admin_route_refuses_a_user(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_denied(client_for_unit_testing, case, CALLERS.user(OWNER), 403)


# The production queue's service is not mocked in the unit client, so an
# admitted request would run against a real database; its router-level guard is
# covered by the two refusal tests above.
ADMIN_ADMITTED = [case for case in ADMIN_ONLY if "/admin/production/" not in case.path]


@pytest.mark.parametrize("case", ADMIN_ADMITTED, ids=str)
async def test_admin_route_admits_an_admin(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_allowed(client_for_unit_testing, case, CALLERS.admin())


@pytest.mark.parametrize(
    "case",
    [
        RouteCase("GET", f"{TEST_API}/orders/{TEST_ORDER_ID}"),
        RouteCase("PATCH", f"{TEST_API}/orders/{TEST_ORDER_ID}/cancel", json={"reason": "not mine"}),
        RouteCase("GET", f"{TEST_API}/orders/user/{OWNER}"),
        # Placing an order in someone else's name.
        RouteCase("POST", f"{TEST_API}/orders", json=_order_payload()),
    ],
    ids=str,
)
async def test_another_users_order_is_refused(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_denied(client_for_unit_testing, case, CALLERS.user(STRANGER), 403)


@pytest.mark.parametrize("case", SIGNED_IN, ids=str)
async def test_owner_is_admitted(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_allowed(client_for_unit_testing, case, CALLERS.user(OWNER))


async def test_stranger_cancel_is_refused_before_anything_changes(
    client_for_unit_testing: AsyncClient, mock_route_order_service
) -> None:
    case = RouteCase("PATCH", f"{TEST_API}/orders/{TEST_ORDER_ID}/cancel", json={"reason": "not mine"})
    await assert_denied(client_for_unit_testing, case, CALLERS.user(STRANGER), 403)
    mock_route_order_service.cancel_order.assert_not_called()
