"""
orders.user_email is stored encrypted, with user_email_hash beside it; the
admin orders table filters by a whole address through that hash. Against the
real order test database, orders written straight to the tables.
"""

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import text

from enums.status_enums import OrderDeliveryStatus, OrderStatus
from infrastructure.managers.test_database_session_manager import TestDatabaseSessionManager
from infrastructure.utils.email_cipher import EmailCipher
from models.order_address_models import OrderAddress
from models.order_models import Order
from tests.constants import TEST_API, TEST_USER_ID

ORDERS = f"{TEST_API}/admin/orders"
ANN = "ann.lee@example.com"
BOB = "bob.stone@example.com"


async def _orders(db: TestDatabaseSessionManager, *emails: str) -> None:
    async with db.transaction() as session:
        for email in emails:
            address = OrderAddress(user_id=TEST_USER_ID, street="1 Main St", city="Calgary",
                                   province="AB", postal_code="T2P 1J9")
            session.add(address)
            await session.flush()
            session.add(Order(user_id=TEST_USER_ID, user_email=email, amount=Decimal("50.00"), currency="cad",
                              status=OrderStatus.CONFIRMED, delivery_status=OrderDeliveryStatus.PENDING,
                              address_id=address.id))


async def test_the_row_holds_ciphertext_and_the_keyed_hash(
    integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager
) -> None:
    await _orders(test_database_session_manager, ANN)
    async with test_database_session_manager.transaction() as session:
        stored, lookup = (await session.execute(text("SELECT user_email, user_email_hash FROM orders"))).one()
    assert stored.startswith("e1.") and "ann" not in stored.lower()
    assert lookup == EmailCipher.current().lookup_hash(ANN)


async def test_the_admin_filter_finds_a_whole_address(
    integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager
) -> None:
    await _orders(test_database_session_manager, ANN, BOB, ANN)
    response = await integration_client.get(ORDERS, params={"user_email": "Ann.Lee@Example.com"})
    assert response.status_code == 200
    assert [row["user_email"] for row in response.json()] == [ANN, ANN]


async def test_part_of_an_address_matches_nothing(
    integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager
) -> None:
    await _orders(test_database_session_manager, ANN, BOB)
    response = await integration_client.get(ORDERS, params={"user_email": "example.com"})
    assert response.status_code == 200
    assert response.json() == []
