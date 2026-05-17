"""Shared test constants for order_service tests."""
from uuid import UUID, uuid4
from datetime import datetime

from shared.enums.status_enums import OrderStatus, OrderDeliveryStatus

TEST_ORDER_ID: UUID = uuid4()
TEST_ORDER_ITEM_ID: UUID = uuid4()
TEST_ORDER_ADDRESS_ID: UUID = uuid4()
TEST_USER_ID: UUID = uuid4()
TEST_PRODUCT_ID: UUID = uuid4()
TEST_PAYMENT_INTENT_ID: str = "pi_test_order_abc123"
TEST_DATETIME: datetime = datetime(2024, 1, 1, 12, 0, 0)
TEST_EMAIL: str = "testorder@example.com"
TEST_AMOUNT: float = 99.99
TEST_CURRENCY: str = "usd"
TEST_API: str = "/api/v1"

MOCK_ORDER_RESULT = {
    "id": str(TEST_ORDER_ID),
    "user_id": str(TEST_USER_ID),
    "user_email": TEST_EMAIL,
    "amount": TEST_AMOUNT,
    "currency": TEST_CURRENCY,
    "status": OrderStatus.PENDING,
    "delivery_status": OrderDeliveryStatus.PENDING,
    "payment_intent_id": TEST_PAYMENT_INTENT_ID,
    "address_id": str(TEST_ORDER_ADDRESS_ID),
    "date_created": TEST_DATETIME.isoformat(),
    "date_updated": None,
}
