"""Unit tests for the in-house production queue's decision logic."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from exceptions.production_exceptions import InvalidProductionTransitionError
from service_layer.order_delivery_status import OrderDeliveryStatusAggregator
from service_layer.production_queue_service import ProductionJobStateMachine
from shared.enums.status_enums import (
    LineFulfillmentStatus,
    OrderDeliveryStatus,
    ProductionJobStatus,
)


def _line(status: LineFulfillmentStatus) -> SimpleNamespace:
    return SimpleNamespace(status=status)


class TestProductionJobStateMachine:
    @pytest.fixture
    def state_machine(self) -> ProductionJobStateMachine:
        return ProductionJobStateMachine()

    @pytest.mark.parametrize(
        "current,target",
        [
            (ProductionJobStatus.QUEUED, ProductionJobStatus.IN_PRODUCTION),
            (ProductionJobStatus.IN_PRODUCTION, ProductionJobStatus.PRINTED),
            (ProductionJobStatus.PRINTED, ProductionJobStatus.SHIPPED),
            (ProductionJobStatus.SHIPPED, ProductionJobStatus.DELIVERED),
            (ProductionJobStatus.QUEUED, ProductionJobStatus.ON_HOLD),
            (ProductionJobStatus.ON_HOLD, ProductionJobStatus.PRINTED),
        ],
    )
    def test_allows_the_normal_workshop_path(
        self, state_machine, current, target
    ) -> None:
        assert state_machine.allows(current, target)

    @pytest.mark.parametrize(
        "current,target",
        [
            # Nothing can be posted before it is printed.
            (ProductionJobStatus.QUEUED, ProductionJobStatus.SHIPPED),
            (ProductionJobStatus.IN_PRODUCTION, ProductionJobStatus.SHIPPED),
            # A delivered or cancelled job is finished for good.
            (ProductionJobStatus.DELIVERED, ProductionJobStatus.SHIPPED),
            (ProductionJobStatus.CANCELLED, ProductionJobStatus.IN_PRODUCTION),
            # A posted parcel cannot be reprinted.
            (ProductionJobStatus.SHIPPED, ProductionJobStatus.PRINTED),
        ],
    )
    def test_refuses_impossible_moves(self, state_machine, current, target) -> None:
        assert not state_machine.allows(current, target)

    def test_ensure_raises_on_an_illegal_move(self, state_machine) -> None:
        job_id = uuid4()
        with pytest.raises(InvalidProductionTransitionError):
            state_machine.ensure(
                job_id, ProductionJobStatus.QUEUED, ProductionJobStatus.DELIVERED
            )

    def test_resume_returns_a_job_to_the_work_already_done(
        self, state_machine
    ) -> None:
        printed = SimpleNamespace(printed_at=object(), started_at=object())
        started = SimpleNamespace(printed_at=None, started_at=object())
        untouched = SimpleNamespace(printed_at=None, started_at=None)

        assert state_machine.resume_target(printed) == ProductionJobStatus.PRINTED
        assert state_machine.resume_target(started) == ProductionJobStatus.IN_PRODUCTION
        assert state_machine.resume_target(untouched) == ProductionJobStatus.QUEUED

    def test_cancelling_printed_or_shipped_work_needs_reconciliation(self) -> None:
        needs_review = ProductionJobStatus.needs_reconciliation_on_cancel()
        assert ProductionJobStatus.PRINTED in needs_review
        assert ProductionJobStatus.SHIPPED in needs_review
        # Nothing has been spent on a job still sitting in the queue.
        assert ProductionJobStatus.QUEUED not in needs_review
        assert ProductionJobStatus.IN_PRODUCTION not in needs_review


class TestOrderDeliveryStatusAggregator:
    @pytest.fixture
    def aggregator(self) -> OrderDeliveryStatusAggregator:
        return OrderDeliveryStatusAggregator()

    def test_no_lines_leaves_the_stored_status_alone(self, aggregator) -> None:
        assert aggregator.aggregate([]) is None

    def test_a_mixed_cart_is_not_dispatched_until_every_line_has_left(
        self, aggregator
    ) -> None:
        # A CJ parcel is on its way but the custom T-shirt is still on the
        # print queue: telling the customer the order is dispatched would be
        # a lie about the half that has not been made yet.
        lines = [
            _line(LineFulfillmentStatus.SHIPPED),
            _line(LineFulfillmentStatus.QUEUED),
        ]
        assert aggregator.aggregate(lines) == OrderDeliveryStatus.PENDING

    def test_a_printed_but_unposted_line_still_holds_the_order_back(
        self, aggregator
    ) -> None:
        lines = [
            _line(LineFulfillmentStatus.SHIPPED),
            _line(LineFulfillmentStatus.PRINTED),
        ]
        assert aggregator.aggregate(lines) == OrderDeliveryStatus.PENDING

    def test_all_lines_shipped_dispatches_the_order(self, aggregator) -> None:
        lines = [
            _line(LineFulfillmentStatus.SHIPPED),
            _line(LineFulfillmentStatus.DELIVERED),
        ]
        assert aggregator.aggregate(lines) == OrderDeliveryStatus.DISPATCHED

    def test_all_lines_delivered_delivers_the_order(self, aggregator) -> None:
        lines = [
            _line(LineFulfillmentStatus.DELIVERED),
            _line(LineFulfillmentStatus.DELIVERED),
        ]
        assert aggregator.aggregate(lines) == OrderDeliveryStatus.DELIVERED

    def test_a_cancelled_line_does_not_hold_the_rest_of_the_order(
        self, aggregator
    ) -> None:
        lines = [
            _line(LineFulfillmentStatus.DELIVERED),
            _line(LineFulfillmentStatus.CANCELLED),
        ]
        assert aggregator.aggregate(lines) == OrderDeliveryStatus.DELIVERED

    def test_every_line_cancelled_cancels_the_order(self, aggregator) -> None:
        lines = [
            _line(LineFulfillmentStatus.CANCELLED),
            _line(LineFulfillmentStatus.CANCELLED),
        ]
        assert aggregator.aggregate(lines) == OrderDeliveryStatus.CANCELLED
