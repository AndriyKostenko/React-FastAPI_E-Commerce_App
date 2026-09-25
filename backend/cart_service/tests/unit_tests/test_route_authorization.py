"""cart-service enforces its own authorisation (bug list 4): a cart is its owner's alone."""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from shared.settings import get_test_settings
from shared.testing.authorization import Callers, RouteCase, assert_allowed, assert_denied
from tests.conftest import SIGNING_KEYS


API = get_test_settings().API
CALLERS = Callers(SIGNING_KEYS)
OWNER, STRANGER, ITEM = uuid4(), uuid4(), uuid4()
CART = f"{API}/users/{OWNER}/cart"
CART_ROUTES = [
    RouteCase("GET", CART),
    RouteCase("GET", f"{CART}/summary"),
    RouteCase("POST", f"{CART}/items", json={"product_id": str(uuid4()), "quantity": 1}),
    RouteCase("PUT", f"{CART}/items/{ITEM}", json={"quantity": 2}),
    RouteCase("DELETE", f"{CART}/items/{ITEM}"),
    RouteCase("DELETE", CART),
]


@pytest.mark.parametrize("case", CART_ROUTES, ids=str)
async def test_anonymous_is_refused(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_denied(client_for_unit_testing, case, CALLERS.anonymous, 401)


@pytest.mark.parametrize("case", CART_ROUTES, ids=str)
async def test_another_users_cart_is_refused(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_denied(client_for_unit_testing, case, CALLERS.user(STRANGER), 403)


@pytest.mark.parametrize("case", CART_ROUTES, ids=str)
async def test_owner_is_admitted(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_allowed(client_for_unit_testing, case, CALLERS.user(OWNER))


@pytest.mark.parametrize("case", CART_ROUTES, ids=str)
async def test_admin_is_admitted(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_allowed(client_for_unit_testing, case, CALLERS.admin())
