"""
payment-service enforces its own authorisation (bug list 4). Reading a payment
used to need only a signed-in user — any user could read any payment by id.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from schemas.payment_schemas import PaymentResponse
from shared.testing.authorization import Callers, RouteCase, assert_allowed, assert_denied
from tests.conftest import SIGNING_KEYS
from tests.constants import (
    TEST_AMOUNT,
    TEST_API,
    TEST_CURRENCY,
    TEST_DATETIME,
    TEST_EMAIL,
    TEST_ORDER_ID,
    TEST_PAYMENT_ID,
    TEST_USER_ID,
)


CALLERS = Callers(SIGNING_KEYS)
OWNER, STRANGER = TEST_USER_ID, uuid4()
GET_PAYMENT = RouteCase("GET", f"{TEST_API}/payments/{TEST_PAYMENT_ID}")
CREATE_INTENT = RouteCase(
    "POST",
    f"{TEST_API}/payments/create-intent",
    json={
        "order_id": str(TEST_ORDER_ID),
        "user_id": str(OWNER),
        "user_email": TEST_EMAIL,
        "amount": TEST_AMOUNT,
        "currency": TEST_CURRENCY,
    },
)


@pytest.fixture(autouse=True)
def owned_payment(mock_route_payment_service) -> None:
    mock_route_payment_service.get_payment_by_id.return_value = PaymentResponse.model_construct(
        id=TEST_PAYMENT_ID,
        order_id=TEST_ORDER_ID,
        user_id=OWNER,
        user_email=TEST_EMAIL,
        stripe_payment_intent_id="pi_test",
        amount=TEST_AMOUNT,
        currency=TEST_CURRENCY,
        status="pending",
        date_created=TEST_DATETIME,
        date_updated=None,
    )


@pytest.mark.parametrize("case", [GET_PAYMENT, CREATE_INTENT, RouteCase("GET", f"{TEST_API}/payments")], ids=str)
async def test_anonymous_is_refused(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_denied(client_for_unit_testing, case, CALLERS.anonymous, 401)


@pytest.mark.parametrize("case", [GET_PAYMENT, CREATE_INTENT], ids=str)
async def test_another_users_payment_is_refused(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_denied(client_for_unit_testing, case, CALLERS.user(STRANGER), 403)


@pytest.mark.parametrize("case", [GET_PAYMENT, CREATE_INTENT], ids=str)
async def test_owner_is_admitted(client_for_unit_testing: AsyncClient, case: RouteCase) -> None:
    await assert_allowed(client_for_unit_testing, case, CALLERS.user(OWNER))


async def test_listing_payments_refuses_a_user(client_for_unit_testing: AsyncClient) -> None:
    await assert_denied(client_for_unit_testing, RouteCase("GET", f"{TEST_API}/payments"), CALLERS.user(OWNER), 403)


async def test_stripe_webhook_needs_no_caller(client_for_unit_testing: AsyncClient) -> None:
    # Stripe authenticates it with its signature, not with a user.
    response = await client_for_unit_testing.post(f"{TEST_API}/payments/webhook", content=b"{}", auth=CALLERS.anonymous)
    assert response.status_code not in (401, 403)
