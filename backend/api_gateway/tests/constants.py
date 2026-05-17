"""Shared test constants for api_gateway tests."""
from uuid import UUID, uuid4

TEST_USER_ID: UUID = uuid4()
TEST_ADMIN_ID: UUID = uuid4()
TEST_USER_EMAIL: str = "user@example.com"
TEST_ADMIN_EMAIL: str = "admin@example.com"
TEST_USER_ROLE: str = "user"
TEST_ADMIN_ROLE: str = "shiba_inu"

TEST_API: str = "/api/v1"
TEST_ORDER_ID: UUID = uuid4()
TEST_PRODUCT_ID: UUID = uuid4()
TEST_NOTIFICATION_ID: UUID = uuid4()
TEST_PAYMENT_ID: UUID = uuid4()
TEST_CATEGORY_ID: UUID = uuid4()
TEST_IMAGE_ID: UUID = uuid4()
TEST_REVIEW_ID: UUID = uuid4()

MOCK_UPSTREAM_RESPONSE_BODY = {"status": "ok", "data": "upstream_result"}
