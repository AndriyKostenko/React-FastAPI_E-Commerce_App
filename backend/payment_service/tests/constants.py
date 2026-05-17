"""Shared test constants for payment_service tests."""
from uuid import UUID, uuid4
from datetime import datetime

from shared.enums.status_enums import PaymentStatus

TEST_PAYMENT_ID: UUID = uuid4()
TEST_ORDER_ID: UUID = uuid4()
TEST_USER_ID: UUID = uuid4()
TEST_STRIPE_INTENT_ID: str = "pi_test_abc123"
TEST_CLIENT_SECRET: str = "pi_test_abc123_secret_xyz"
TEST_DATETIME: datetime = datetime(2024, 1, 1, 12, 0, 0)
TEST_EMAIL: str = "testuser@example.com"
TEST_AMOUNT: int = 9999  # cents
TEST_CURRENCY: str = "usd"
TEST_API: str = "/api/v1"

MOCK_PAYMENT_INTENT_RESULT = {
    "client_secret": TEST_CLIENT_SECRET,
    "stripe_payment_intent_id": TEST_STRIPE_INTENT_ID,
    "payment_id": str(TEST_PAYMENT_ID),
    "order_id": str(TEST_ORDER_ID),
}
