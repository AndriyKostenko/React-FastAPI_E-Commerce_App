"""Events carry bounded values: identifiers and lists are refused past a bound, free text is clipped."""
from uuid import uuid4

import pytest
from pydantic import ValidationError

from contracts.events import CJOrderPaidEvent, OrderCancelledEvent, OrderCreatedEvent
from contracts.limits import IDENTIFIER_MAX_LENGTH, LINES_MAX, OBJECT_KEYS_MAX, TEXT_MAX_LENGTH
from contracts.order import OrderItem


def _order_fields() -> dict:
    return {"order_id": uuid4(), "user_id": uuid4(), "user_email": "shopper@example.com"}


def _item(**overrides) -> dict:
    return {"order_id": uuid4(), "product_id": uuid4(), "quantity": 1, "price": 20.0, **overrides}


class TestFreeTextIsClipped:
    def test_a_long_reason_is_cut_to_the_bound_rather_than_refused(self):
        # A reason is often an exception's text; an over-long one must not stop the saga step.
        event = OrderCancelledEvent(**_order_fields(), reason="x" * (TEXT_MAX_LENGTH * 3))

        assert len(event.reason) == TEXT_MAX_LENGTH

    def test_a_consumer_reading_the_published_json_gets_the_same_clipped_text(self):
        published = OrderCancelledEvent(**_order_fields(), reason="y" * (TEXT_MAX_LENGTH + 10)).model_dump_json()

        consumed = OrderCancelledEvent.model_validate_json(published)

        assert consumed.reason == "y" * TEXT_MAX_LENGTH

    def test_a_short_reason_is_left_as_it_is(self):
        assert OrderCancelledEvent(**_order_fields(), reason="Payment failed").reason == "Payment failed"

    def test_a_reason_that_is_not_text_is_still_refused(self):
        with pytest.raises(ValidationError):
            OrderCancelledEvent(**_order_fields(), reason=["not", "text"])


class TestOtherValuesAreRefused:
    def test_an_identifier_past_the_bound(self):
        with pytest.raises(ValidationError, match="cj_order_number"):
            CJOrderPaidEvent(**_order_fields(), cj_order_number="C" * (IDENTIFIER_MAX_LENGTH + 1))

    def test_more_lines_than_an_order_holds(self):
        with pytest.raises(ValidationError, match="items"):
            OrderCreatedEvent(**_order_fields(), items=[_item()] * (LINES_MAX + 1), total_amount=20.0)

    def test_a_variant_snapshot_with_more_keys_than_any_variant_has(self):
        snapshot = {f"key{index}": index for index in range(OBJECT_KEYS_MAX + 1)}

        with pytest.raises(ValidationError, match="variant_snapshot"):
            OrderItem(**_item(variant_snapshot=snapshot))

    def test_an_event_type_past_the_bound(self):
        with pytest.raises(ValidationError, match="event_type"):
            OrderCancelledEvent(**_order_fields(), reason="r", event_type="e" * 65)

    def test_a_full_order_at_every_bound_is_accepted(self):
        event = OrderCreatedEvent(**_order_fields(), items=[_item()] * LINES_MAX, total_amount=20.0)

        assert len(OrderCreatedEvent.model_validate_json(event.model_dump_json()).items) == LINES_MAX
