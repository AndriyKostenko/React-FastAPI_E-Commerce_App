"""Test constants for payment_service — sourced from shared TestSettings."""
from shared.shared_instances import test_settings

TEST_PAYMENT_ID       = test_settings.TEST_PAYMENT_ID
TEST_ORDER_ID         = test_settings.TEST_ORDER_ID
TEST_USER_ID          = test_settings.TEST_USER_ID
TEST_STRIPE_INTENT_ID = test_settings.TEST_STRIPE_INTENT_ID
TEST_CLIENT_SECRET    = test_settings.TEST_CLIENT_SECRET
TEST_DATETIME         = test_settings.TEST_DATETIME
TEST_EMAIL            = test_settings.TEST_EMAIL
TEST_AMOUNT           = test_settings.TEST_AMOUNT_CENTS  # payment amounts are in cents
TEST_CURRENCY         = test_settings.TEST_CURRENCY
TEST_API              = test_settings.API

MOCK_PAYMENT_INTENT_RESULT = test_settings.MOCK_PAYMENT_INTENT_RESULT
