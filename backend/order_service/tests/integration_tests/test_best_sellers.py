"""
GET /best-sellers against the real order test database.

Orders, lines and refunds are written straight to the tables, so each test
states exactly which sales exist: paid or not, inside the window or not,
catalogue or custom, refunded or not.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from enums.status_enums import OrderDeliveryStatus, OrderStatus
from httpx import AsyncClient
from infrastructure.managers.test_database_session_manager import (
    TestDatabaseSessionManager,
)
from infrastructure.testing.signing_keys import ANONYMOUS
from models.order_address_models import OrderAddress
from models.order_fulfillment_models import OrderLineFulfillment
from models.order_item_models import OrderItem
from models.order_models import Order
from models.order_refund_models import OrderRefund
from service_layer.order_refund_service import RefundState

from tests.constants import TEST_API, TEST_USER_ID

URL = f"{TEST_API}/best-sellers"

TEE = uuid4()
HOODIE = uuid4()
CAP = uuid4()
CUSTOM_BLANK = uuid4()


async def _order(
    db: TestDatabaseSessionManager,
    lines: list[tuple[UUID, int, str]],
    *,
    status: OrderStatus = OrderStatus.CONFIRMED,
    age_days: float = 1,
) -> list[UUID]:
    """One order with the given (product, quantity, fulfillment type) lines; returns the line ids."""
    placed = datetime.now(UTC) - timedelta(days=age_days)
    async with db.transaction() as session:
        address = OrderAddress(
            user_id=TEST_USER_ID,
            street="1 Main St",
            city="Calgary",
            province="AB",
            postal_code="T2P 1J9",
        )
        session.add(address)
        await session.flush()
        order = Order(
            user_id=TEST_USER_ID,
            user_email="buyer@example.com",
            amount=Decimal("50.00"),
            currency="cad",
            status=status,
            delivery_status=OrderDeliveryStatus.PENDING,
            address_id=address.id,
            date_created=placed,
        )
        session.add(order)
        await session.flush()
        item_ids: list[UUID] = []
        for product_id, quantity, fulfillment_type in lines:
            item = OrderItem(
                order_id=order.id,
                product_id=product_id,
                quantity=quantity,
                price=Decimal("25.00"),
            )
            session.add(item)
            await session.flush()
            session.add(
                OrderLineFulfillment(
                    order_item_id=item.id,
                    fulfillment_type=fulfillment_type,
                    product_name="tee",
                )
            )
            item_ids.append(item.id)
        return item_ids


async def _refund(
    db: TestDatabaseSessionManager, item_id: UUID, quantity: int, status: RefundState
) -> None:
    async with db.transaction() as session:
        item = await session.get(OrderItem, item_id)
        session.add(
            OrderRefund(
                order_id=item.order_id,
                amount=Decimal("25.00") * quantity,
                lines=[
                    {
                        "order_item_id": str(item_id),
                        "quantity": quantity,
                        "amount": "25.00",
                    }
                ],
                reason="returned",
                status=status,
            )
        )


async def _ranking(client: AsyncClient, **params: int) -> list[tuple[UUID, int]]:
    response = await client.get(URL, params=params)
    assert response.status_code == 200, response.text
    return [(UUID(row["product_id"]), row["units_sold"]) for row in response.json()]


async def test_products_rank_by_units_across_orders(
    integration_client: AsyncClient,
    test_database_session_manager: TestDatabaseSessionManager,
) -> None:
    db = test_database_session_manager
    await _order(db, [(TEE, 2, "cj"), (HOODIE, 1, "catalog")])
    await _order(db, [(TEE, 1, "cj"), (HOODIE, 1, "catalog"), (CAP, 1, "cj")])

    assert await _ranking(integration_client) == [(TEE, 3), (HOODIE, 2), (CAP, 1)]


async def test_only_paid_orders_count(
    integration_client: AsyncClient,
    test_database_session_manager: TestDatabaseSessionManager,
) -> None:
    db = test_database_session_manager
    await _order(db, [(TEE, 5, "cj")], status=OrderStatus.PENDING)
    await _order(db, [(TEE, 5, "cj")], status=OrderStatus.CANCELLED)
    await _order(db, [(HOODIE, 1, "cj")])

    assert await _ranking(integration_client) == [(HOODIE, 1)]


async def test_sales_before_the_window_do_not_count(
    integration_client: AsyncClient,
    test_database_session_manager: TestDatabaseSessionManager,
) -> None:
    db = test_database_session_manager
    await _order(db, [(TEE, 4, "cj")], age_days=31)
    await _order(db, [(HOODIE, 1, "cj")], age_days=29)

    assert await _ranking(integration_client) == [(HOODIE, 1)]
    # A longer window takes the older sale in.
    assert await _ranking(integration_client, days=90) == [(TEE, 4), (HOODIE, 1)]


async def test_custom_designs_are_left_out(
    integration_client: AsyncClient,
    test_database_session_manager: TestDatabaseSessionManager,
) -> None:
    db = test_database_session_manager
    await _order(db, [(CUSTOM_BLANK, 6, "custom"), (TEE, 1, "cj")])

    assert await _ranking(integration_client) == [(TEE, 1)]


async def test_refunded_units_are_taken_off(
    integration_client: AsyncClient,
    test_database_session_manager: TestDatabaseSessionManager,
) -> None:
    db = test_database_session_manager
    tee_line, hoodie_line = await _order(db, [(TEE, 3, "cj"), (HOODIE, 2, "catalog")])
    (cap_line,) = await _order(db, [(CAP, 1, "cj")])
    await _refund(db, tee_line, 2, RefundState.SUCCEEDED)
    # A refund still waiting on Stripe counts already; a failed one gave nothing back.
    await _refund(db, cap_line, 1, RefundState.REQUESTED)
    await _refund(db, hoodie_line, 2, RefundState.FAILED)

    assert await _ranking(integration_client) == [(HOODIE, 2), (TEE, 1)]


async def test_a_refund_never_takes_a_line_below_zero(
    integration_client: AsyncClient,
    test_database_session_manager: TestDatabaseSessionManager,
) -> None:
    db = test_database_session_manager
    (over_refunded,) = await _order(db, [(TEE, 1, "cj")])
    await _order(db, [(TEE, 2, "cj")])
    # Two refunds of the same unit (one recorded per return and one by an admin)
    # must not eat into the other order's units.
    await _refund(db, over_refunded, 1, RefundState.SUCCEEDED)
    await _refund(db, over_refunded, 1, RefundState.SUCCEEDED)

    assert await _ranking(integration_client) == [(TEE, 2)]


async def test_limit_keeps_the_top(
    integration_client: AsyncClient,
    test_database_session_manager: TestDatabaseSessionManager,
) -> None:
    db = test_database_session_manager
    await _order(db, [(TEE, 3, "cj"), (HOODIE, 2, "cj"), (CAP, 1, "cj")])

    assert await _ranking(integration_client, limit=2) == [(TEE, 3), (HOODIE, 2)]


async def test_anyone_may_read_it(
    integration_client: AsyncClient,
    test_database_session_manager: TestDatabaseSessionManager,
) -> None:
    await _order(test_database_session_manager, [(TEE, 1, "cj")])

    response = await integration_client.get(URL, auth=ANONYMOUS)

    assert response.status_code == 200
    # Product ids and counts only: nothing about who bought.
    assert response.json() == [{"product_id": str(TEE), "units_sold": 1}]


@pytest.mark.parametrize(
    "params", [{"days": 0}, {"days": 366}, {"limit": 0}, {"limit": 51}]
)
async def test_out_of_range_parameters_are_refused(
    integration_client: AsyncClient, params: dict[str, int]
) -> None:
    response = await integration_client.get(URL, params=params)

    assert response.status_code == 422
