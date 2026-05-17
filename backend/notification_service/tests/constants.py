"""Shared test constants for notification_service tests."""
from uuid import UUID, uuid4
from datetime import datetime

TEST_NOTIFICATION_ID: UUID = uuid4()
TEST_USER_ID: UUID = uuid4()
TEST_NOTIFICATION_TYPE: str = "user.registered"
TEST_MESSAGE: str = "Welcome! Please verify your email address."
TEST_DATETIME: datetime = datetime(2024, 6, 1, 10, 0, 0)
TEST_EMAIL: str = "testnotif@example.com"
TEST_ORDER_ID: UUID = uuid4()
TEST_EVENT_ID: str = str(uuid4())
TEST_API: str = "/api/v1"

MOCK_NOTIFICATION_RESULT = {
    "id": str(TEST_NOTIFICATION_ID),
    "user_id": str(TEST_USER_ID),
    "message": TEST_MESSAGE,
    "notification_type": TEST_NOTIFICATION_TYPE,
    "is_read": False,
    "date_created": TEST_DATETIME.isoformat(),
    "date_updated": None,
}
