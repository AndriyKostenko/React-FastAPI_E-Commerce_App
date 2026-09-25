"""
notification-service enforces its own authorisation (bug list 4). The per-user
listing routes trusted the gateway alone; the per-notification routes already
checked ownership in the service and still do.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from shared.testing.authorization import Callers, RouteCase, assert_allowed, assert_denied
from tests.conftest import SIGNING_KEYS
from tests.constants import TEST_API


CALLERS = Callers(SIGNING_KEYS)
OWNER, STRANGER = uuid4(), uuid4()
PER_USER = [
    RouteCase("GET", f"{TEST_API}/notifications/users/{OWNER}"),
    RouteCase("GET", f"{TEST_API}/notifications/users/{OWNER}/unread-count"),
    RouteCase("PATCH", f"{TEST_API}/notifications/users/{OWNER}/read-all"),
]


@pytest.mark.parametrize("case", PER_USER, ids=str)
async def test_anonymous_is_refused(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_denied(client_for_unit_testing, case, CALLERS.anonymous, 401)


@pytest.mark.parametrize("case", PER_USER, ids=str)
async def test_another_users_notifications_are_refused(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_denied(client_for_unit_testing, case, CALLERS.user(STRANGER), 403)


@pytest.mark.parametrize("case", PER_USER, ids=str)
async def test_owner_is_admitted(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_allowed(client_for_unit_testing, case, CALLERS.user(OWNER))
