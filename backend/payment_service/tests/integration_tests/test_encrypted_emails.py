"""
payments.user_email is stored encrypted and read back in plain text, against
the real payment test database. Nothing looks a payment up by address.
"""

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select, text

from infrastructure.managers.test_database_session_manager import TestDatabaseSessionManager
from models.payment_models import Payment

BUYER = "ann.lee@example.com"


async def test_the_address_is_stored_encrypted_and_read_back(
    integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager
) -> None:
    async with test_database_session_manager.transaction() as session:
        session.add(Payment(order_id=uuid4(), user_id=uuid4(), user_email=BUYER, stripe_payment_intent_id="pi_enc",
                            amount=5_000, currency="cad", status="requires_capture"))
    async with test_database_session_manager.transaction() as session:
        stored = (await session.execute(text("SELECT user_email FROM payments"))).scalar_one()
        payment = (await session.execute(select(Payment))).scalar_one()
    assert stored.startswith("e1.") and "ann" not in stored.lower()
    assert payment.user_email == BUYER
