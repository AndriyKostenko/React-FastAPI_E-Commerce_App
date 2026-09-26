"""
Stripe Tax against the real payment test database: which tax records a
capture and a refund leave behind. Only Stripe is replaced, by a fake that
records every tax call it receives.
"""

from collections.abc import AsyncGenerator
from logging import getLogger
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import stripe
from httpx import AsyncClient
from sqlalchemy import select

from database_layer.payment_repository import PaymentRepository
from models.base import Base
from models.outbox_models import OutboxEvent
from models.payment_models import Payment
from service_layer.outbox_event_service import OutboxEventService
from service_layer.payment_refund_service import PaymentRefundService, RefundStatus
from service_layer.payment_service import PaymentService
from service_layer.tax_service import TaxCalculationService, TaxLocationInvalidError
from shared.contracts.events import PaymentRefundRequested
from shared.contracts.tax import TaxAddress, TaxCalculationRequest, TaxLine
from shared.database_layer.outbox_repository import OutboxRepository
from shared.enums.status_enums import PaymentStatus
from shared.managers.test_database_session_manager import TestDatabaseSessionManager
from shared.testing.signing_keys import ANONYMOUS, EphemeralSigningKeys
from dependencies.dependencies import get_tax_calculation_service
from main import app
from tests.conftest import DEFAULT_CALLER, SIGNING_KEYS
from tests.constants import TEST_API


pytestmark = pytest.mark.asyncio(loop_scope="session")
AMOUNT = 11_300  # $113.00: $100.00 of goods + $13.00 tax


class FakeStripe:
    """Records captures, refunds and every Stripe Tax call."""

    def __init__(self) -> None:
        self.captures: list[dict[str, object] | None] = []
        self.sales: list[dict[str, object]] = []
        self.reversals: list[dict[str, object]] = []
        self.calculations: list[dict[str, object]] = []
        self.calculation_error: Exception | None = None
        self.v1 = SimpleNamespace(
            payment_intents=SimpleNamespace(capture_async=self._capture),
            refunds=SimpleNamespace(create_async=self._refund),
            tax=SimpleNamespace(
                calculations=SimpleNamespace(create_async=self._calculate),
                transactions=SimpleNamespace(
                    create_from_calculation_async=self._sale,
                    create_reversal_async=self._reversal,
                ),
            ),
        )

    async def _capture(self, intent_id: str, params: dict[str, object] | None, options: dict[str, str]) -> None:
        self.captures.append(params)

    async def _refund(self, params: dict[str, object], options: dict[str, str]) -> SimpleNamespace:
        return SimpleNamespace(id=f"re_{uuid4().hex[:8]}")

    async def _calculate(self, params: dict[str, object]) -> SimpleNamespace:
        if self.calculation_error is not None:
            raise self.calculation_error
        self.calculations.append(params)
        return SimpleNamespace(id="taxcalc_1", tax_amount_exclusive=1_300, amount_total=AMOUNT)

    async def _sale(self, params: dict[str, object], options: dict[str, str]) -> SimpleNamespace:
        self.sales.append(params)
        return SimpleNamespace(id="tax_sale_1")

    async def _reversal(self, params: dict[str, object], options: dict[str, str]) -> SimpleNamespace:
        self.reversals.append(params)
        return SimpleNamespace(id=f"tax_rev_{len(self.reversals)}")


_SETTINGS = SimpleNamespace(
    STRIPE_API_KEY="sk_test_unused",
    STRIPE_WEBHOOK_SIGNING_SECRET="whsec_unused",
    FULL_STRIPE_WEBHOOK_ENDPOINT="https://example.test/webhook",
    STRIPE_MAX_NETWORK_RETRIES=0,
    STRIPE_TAX_PRODUCT_TAX_CODE="txcd_30011000",
)


@pytest.fixture
async def db(test_database_session_manager: TestDatabaseSessionManager) -> AsyncGenerator[TestDatabaseSessionManager, None]:
    await test_database_session_manager.init_db(Base.metadata)
    yield test_database_session_manager
    await test_database_session_manager.truncate_all_tables(Base.metadata)


async def _payment(
    db: TestDatabaseSessionManager,
    status: PaymentStatus,
    *,
    taxed: bool = True,
    capture_reduction_cents: int = 0,
    tax_transaction_id: str | None = None,
) -> UUID:
    order_id = uuid4()
    async with db.transaction() as session:
        session.add(Payment(
            order_id=order_id, user_id=uuid4(), user_email="buyer@example.com",
            stripe_payment_intent_id=f"pi_{uuid4().hex}", amount=AMOUNT, currency="cad", status=status,
            capture_reduction_cents=capture_reduction_cents,
            tax_calculation_id="taxcalc_1" if taxed else None,
            tax_transaction_id=tax_transaction_id,
        ))
    return order_id


async def _capture(db: TestDatabaseSessionManager, fake: FakeStripe, order_id: UUID) -> None:
    async with db.transaction() as session:
        await PaymentService(
            repository=PaymentRepository(session),
            outbox_event_service=OutboxEventService(OutboxRepository(session=session, model=OutboxEvent)),
            settings=_SETTINGS,
            logger=getLogger("t"),
            stripe_client=fake,
        ).capture_payment(order_id)


async def _stored(db: TestDatabaseSessionManager, order_id: UUID) -> Payment:
    async with db.transaction() as session:
        return (await session.execute(select(Payment).where(Payment.order_id == order_id))).scalar_one()


# ------------------------------------------------------------------ capture


async def test_capture_records_the_tax_sale_once(db) -> None:
    order_id = await _payment(db, PaymentStatus.AUTHORIZED)
    fake = FakeStripe()

    await _capture(db, fake, order_id)
    await _capture(db, fake, order_id)  # a redelivered capture command

    assert fake.sales == [{"calculation": "taxcalc_1", "reference": f"order_{order_id}"}]
    assert fake.reversals == []
    assert (await _stored(db, order_id)).tax_transaction_id == "tax_sale_1"


async def test_a_reduced_capture_reverses_the_tax_on_what_was_not_charged(db) -> None:
    """Lines refunded before capture were never charged, so neither was their tax."""
    order_id = await _payment(db, PaymentStatus.AUTHORIZED, capture_reduction_cents=2_260)
    fake = FakeStripe()

    await _capture(db, fake, order_id)

    assert fake.captures == [{"amount_to_capture": AMOUNT - 2_260}]
    assert fake.reversals == [{
        "mode": "partial",
        "original_transaction": "tax_sale_1",
        "reference": f"order_{order_id}-not_captured",
        "flat_amount": -2_260,
    }]


async def test_an_untaxed_payment_leaves_no_tax_records(db) -> None:
    order_id = await _payment(db, PaymentStatus.AUTHORIZED, taxed=False)
    fake = FakeStripe()

    await _capture(db, fake, order_id)

    assert fake.sales == [] and fake.reversals == []
    assert (await _stored(db, order_id)).status == PaymentStatus.SUCCEEDED


# ------------------------------------------------------------------ refunds


def _command(order_id: UUID, cents: int) -> PaymentRefundRequested:
    return PaymentRefundRequested(
        order_id=order_id, user_id=uuid4(), user_email="buyer@example.com",
        refund_id=uuid4(), amount_cents=cents, reason="damaged item",
    )


async def test_a_refund_reverses_its_amount_in_the_tax_records(db) -> None:
    order_id = await _payment(db, PaymentStatus.SUCCEEDED, tax_transaction_id="tax_sale_1")
    fake = FakeStripe()
    command = _command(order_id, 5_650)

    assert await PaymentRefundService(db, fake, getLogger("t")).refund(command) == RefundStatus.SUCCEEDED

    assert fake.reversals == [{
        "mode": "partial",
        "original_transaction": "tax_sale_1",
        "reference": f"refund_{command.refund_id}",
        "flat_amount": -5_650,
    }]


async def test_a_reduction_before_capture_is_left_to_the_capture(db) -> None:
    order_id = await _payment(db, PaymentStatus.AUTHORIZED)
    fake = FakeStripe()

    status = await PaymentRefundService(db, fake, getLogger("t")).refund(_command(order_id, 2_260))

    assert status == RefundStatus.REDUCED_CAPTURE
    assert fake.reversals == []  # no sale exists yet; capture reverses it


# -------------------------------------------------------------- calculation


def _tax_request(**address: str) -> TaxCalculationRequest:
    return TaxCalculationRequest(
        currency="CAD",
        lines=[TaxLine(reference="L0-shirt", amount_cents=10_000, quantity=2)],
        shipping_cents=999,
        address=TaxAddress(country="CA", postal_code="T1T 1T1", state="AB", **address),
    )


async def test_a_calculation_prices_tax_exclusive_lines_and_shipping() -> None:
    fake = FakeStripe()

    result = await TaxCalculationService(fake, _SETTINGS).calculate(_tax_request())

    assert (result.calculation_id, result.tax_cents, result.total_cents) == ("taxcalc_1", 1_300, AMOUNT)
    assert fake.calculations == [{
        "currency": "cad",
        "line_items": [{
            "amount": 10_000, "quantity": 2, "reference": "L0-shirt",
            "tax_behavior": "exclusive", "tax_code": "txcd_30011000",
        }],
        "customer_details": {
            "address": {"country": "CA", "postal_code": "T1T 1T1", "state": "AB"},
            "address_source": "shipping",
        },
        "shipping_cost": {"amount": 999},
    }]


async def test_an_address_stripe_cannot_place_is_the_customers_to_fix() -> None:
    fake = FakeStripe()
    fake.calculation_error = stripe.InvalidRequestError(
        "location invalid", param="customer_details", code="customer_tax_location_invalid"
    )

    with pytest.raises(TaxLocationInvalidError):
        await TaxCalculationService(fake, _SETTINGS).calculate(_tax_request())


# ------------------------------------------------------------------ route


@pytest.mark.parametrize(
    ("caller", "why"),
    [
        (ANONYMOUS, "anyone who reaches the service directly"),
        (DEFAULT_CALLER, "a user, even an admin, through the gateway"),
        (EphemeralSigningKeys().order_service_auth(), "someone without order-service's key"),
    ],
    ids=["anonymous", "admin-user", "forged-key"],
)
async def test_only_order_service_may_calculate_tax(client_for_unit_testing: AsyncClient, caller, why: str) -> None:
    response = await client_for_unit_testing.post(f"{TEST_API}/payments/tax/calculate", json={}, auth=caller)
    assert response.status_code == 401, why


async def test_order_service_gets_past_the_tax_guard(client_for_unit_testing: AsyncClient) -> None:
    app.dependency_overrides[get_tax_calculation_service] = lambda: TaxCalculationService(FakeStripe(), _SETTINGS)
    response = await client_for_unit_testing.post(
        f"{TEST_API}/payments/tax/calculate", json={}, auth=SIGNING_KEYS.order_service_auth()
    )
    # Past authentication; the empty body is then rejected by validation.
    assert response.status_code == 422
