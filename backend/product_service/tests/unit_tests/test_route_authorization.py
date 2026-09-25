"""
product-service enforces its own authorisation (bug list 4): catalogue writes
are admin-only, reviews belong to their author, reads stay public.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from shared.settings import get_test_settings
from shared.testing.authorization import Callers, RouteCase, assert_allowed, assert_denied
from tests.conftest import SIGNING_KEYS


API = get_test_settings().API
CALLERS = Callers(SIGNING_KEYS)
AUTHOR, STRANGER = uuid4(), uuid4()
PRODUCT, CATEGORY, IMAGE = uuid4(), uuid4(), uuid4()

ADMIN_ONLY = [
    RouteCase("POST", f"{API}/products", json={}),
    RouteCase("POST", f"{API}/products/upload"),
    RouteCase("PATCH", f"{API}/products/{PRODUCT}", json={}),
    RouteCase("DELETE", f"{API}/products/{PRODUCT}"),
    RouteCase("POST", f"{API}/categories", json={}),
    RouteCase("POST", f"{API}/categories/upload"),
    RouteCase("PATCH", f"{API}/categories/{CATEGORY}", json={}),
    RouteCase("DELETE", f"{API}/categories/{CATEGORY}"),
    RouteCase("POST", f"{API}/{PRODUCT}/images"),
    RouteCase("PUT", f"{API}/{PRODUCT}/images"),
    RouteCase("PATCH", f"{API}/images/{IMAGE}", json={}),
    RouteCase("DELETE", f"{API}/images/{IMAGE}"),
]
REVIEW = f"{API}/products/{PRODUCT}/users/{AUTHOR}/reviews"
AUTHOR_ONLY = [
    RouteCase("POST", REVIEW, json={"rating": 5, "comment": "great"}),
    RouteCase("PUT", REVIEW, json={"rating": 4, "comment": "good"}),
    RouteCase("DELETE", REVIEW),
]
PUBLIC_READS = [
    RouteCase("GET", f"{API}/products"),
    RouteCase("GET", f"{API}/categories"),
    RouteCase("GET", f"{API}/reviews"),
]


@pytest.mark.parametrize("case", ADMIN_ONLY + AUTHOR_ONLY, ids=str)
async def test_anonymous_is_refused(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_denied(client_for_unit_testing, case, CALLERS.anonymous, 401)


@pytest.mark.parametrize("case", ADMIN_ONLY, ids=str)
async def test_catalogue_write_refuses_a_user(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_denied(client_for_unit_testing, case, CALLERS.user(AUTHOR), 403)


@pytest.mark.parametrize("case", AUTHOR_ONLY, ids=str)
async def test_review_refuses_someone_writing_as_another_user(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_denied(client_for_unit_testing, case, CALLERS.user(STRANGER), 403)


@pytest.mark.parametrize("case", AUTHOR_ONLY, ids=str)
async def test_review_admits_its_author(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_allowed(client_for_unit_testing, case, CALLERS.user(AUTHOR))


@pytest.mark.parametrize("case", PUBLIC_READS, ids=str)
async def test_catalogue_reads_stay_public(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_allowed(client_for_unit_testing, case, CALLERS.anonymous)
