"""Unit tests for supplier_service event consumer."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from event_consumer.supplier_event_consumer import SupplierEventConsumer
from enums.cj_order_enums import CJOrderAttemptStatus
from exceptions.cj_order_exceptions import CJOrderCreationError, CJOrderAmbiguousError
from service_layer.cj_api_client import CJDropshippingAPIError
from service_layer.product_service_client import ProductServiceError
from shared.enums.event_enums import InventoryEvents, OrderEvents, SupplierEvents
from shared.settings import get_settings
from shared.contracts.events import SupplierProductImportCompletedEvent


TEST_ORDER_ID = uuid4()
TEST_USER_ID = uuid4()
TEST_PRODUCT_ID = uuid4()
TEST_VARIANT_ID = uuid4()
TEST_PID = "CJPID123"
TEST_VID = "CJVID456"
TEST_CJ_ORDER_NUMBER = "CJORDER789"


def _make_consumer(
    *,
    claim_event: bool = True,
    resolve_cj_ids: tuple[str, str] | Exception | None = None,
    create_order_response: dict | Exception | None = None,
):
    logger = MagicMock()
    idempotency = MagicMock()
    idempotency.try_claim_event = AsyncMock(return_value=claim_event)
    idempotency.mark_event_as_processed = AsyncMock()
    idempotency.release_claim = AsyncMock()

    cj_client = MagicMock()
    cj_client.get_order_detail = AsyncMock(
        return_value={"result": False, "code": 1600300, "data": None}
    )
    if isinstance(create_order_response, Exception):
        cj_client.create_order_v2 = AsyncMock(side_effect=create_order_response)
    else:
        cj_client.create_order_v2 = AsyncMock(return_value=create_order_response)

    product_client = MagicMock()
    if isinstance(resolve_cj_ids, Exception):
        product_client.resolve_cj_ids = AsyncMock(side_effect=resolve_cj_ids)
    else:
        product_client.resolve_cj_ids = AsyncMock(return_value=resolve_cj_ids)

    publisher = MagicMock()
    publisher.publish_cj_order_created = AsyncMock()
    publisher.publish_order_cancelled = AsyncMock()
    publisher.publish_inventory_release_requested = AsyncMock()

    consumer = SupplierEventConsumer(
        logger=logger,
        settings=get_settings(),
        database=MagicMock(),
        idempotency_service=idempotency,
        cj_api_client=cj_client,
        product_service_client=product_client,
        publisher=publisher,
    )
    consumer.inventory_verifier.verify_variant_stock = AsyncMock(
        return_value=SimpleNamespace(sufficient=True, buffered_available=100)
    )
    consumer._get_attempt = AsyncMock(return_value=None)
    consumer._record_creating = AsyncMock()
    consumer._record_created = AsyncMock()
    consumer._record_failed = AsyncMock()
    consumer._mark_reconciliation = AsyncMock()
    consumer.payment_service.advance = AsyncMock(return_value=CJOrderAttemptStatus.PAID)
    return consumer


def _make_order_confirmed_message(**overrides) -> dict:
    message = {
        "event_id": str(uuid4()),
        "timestamp": "2026-07-14T00:00:00+00:00",
        "service": "order-service",
        "event_type": OrderEvents.ORDER_CONFIRMED,
        "order_id": str(TEST_ORDER_ID),
        "user_id": str(TEST_USER_ID),
        "user_email": "test@example.com",
        "items": [
            {
                "product_id": str(TEST_PRODUCT_ID),
                "variant_id": str(TEST_VARIANT_ID),
                "quantity": 2,
                "price": 49.99,
                "fulfillment_type": "cj",
            }
        ],
        "address": {
            "street": "123 Test St",
            "city": "Testville",
            "province": "TS",
            "postal_code": "T1T 1T1",
            "country": "Canada",
            "country_code": "CA",
            "name": "Test User",
            "phone": "+1234567890",
        },
    }
    message.update(overrides)
    return message


class TestHandleOrderConfirmed:
    async def test_non_cj_lines_are_ignored(self):
        consumer = _make_consumer(resolve_cj_ids=(TEST_PID, TEST_VID))
        message = _make_order_confirmed_message()
        message["items"][0]["fulfillment_type"] = "custom"

        await consumer.handle_order_confirmed(message)

        consumer.product_service_client.resolve_cj_ids.assert_not_awaited()
        consumer.cj_api_client.create_order_v2.assert_not_awaited()

    async def test_creates_cj_order_and_publishes_event(self):
        consumer = _make_consumer(
            resolve_cj_ids=(TEST_PID, TEST_VID),
            create_order_response={
                "result": True,
                "code": 200,
                "data": {"orderId": TEST_CJ_ORDER_NUMBER},
            },
        )

        await consumer.handle_order_confirmed(_make_order_confirmed_message())

        consumer.product_service_client.resolve_cj_ids.assert_awaited_once_with(
            product_id=TEST_PRODUCT_ID,
            variant_id=TEST_VARIANT_ID,
        )
        consumer.inventory_verifier.verify_variant_stock.assert_awaited_once_with(
            TEST_VID, 2
        )
        consumer.cj_api_client.create_order_v2.assert_awaited_once()
        consumer._record_created.assert_awaited_once_with(
            ANY, TEST_CJ_ORDER_NUMBER
        )
        consumer.publisher.publish_order_cancelled.assert_not_awaited()
        consumer.publisher.publish_inventory_release_requested.assert_not_awaited()

    async def test_created_cj_order_is_paid_straight_away(self):
        consumer = _make_consumer(
            resolve_cj_ids=(TEST_PID, TEST_VID),
            create_order_response={
                "result": True,
                "code": 200,
                "data": {"orderId": TEST_CJ_ORDER_NUMBER},
            },
        )

        await consumer.handle_order_confirmed(_make_order_confirmed_message())

        consumer.payment_service.advance.assert_awaited_once_with(TEST_ORDER_ID)

    async def test_deferred_payment_does_not_fail_the_created_order(self):
        from service_layer.cj_order_payment_service import CJPaymentPending

        consumer = _make_consumer(
            resolve_cj_ids=(TEST_PID, TEST_VID),
            create_order_response={
                "result": True,
                "code": 200,
                "data": {"orderId": TEST_CJ_ORDER_NUMBER},
            },
        )
        consumer.payment_service.advance = AsyncMock(side_effect=CJPaymentPending("CJ busy"))

        await consumer.handle_order_confirmed(_make_order_confirmed_message())

        consumer._record_failed.assert_not_awaited()
        consumer.idempotency_service.release_claim.assert_not_awaited()

    async def test_duplicate_event_is_skipped(self):
        consumer = _make_consumer(claim_event=False)

        await consumer.handle_order_confirmed(_make_order_confirmed_message())

        consumer.product_service_client.resolve_cj_ids.assert_not_awaited()
        consumer.cj_api_client.create_order_v2.assert_not_awaited()
        consumer.publisher.publish_cj_order_created.assert_not_awaited()

    async def test_ambiguous_cj_api_failure_never_compensates(self):
        consumer = _make_consumer(
            resolve_cj_ids=(TEST_PID, TEST_VID),
            create_order_response=CJDropshippingAPIError("CJ API error"),
        )

        with pytest.raises(CJOrderAmbiguousError):
            await consumer.handle_order_confirmed(_make_order_confirmed_message())

        consumer.publisher.publish_cj_order_created.assert_not_awaited()
        consumer._record_failed.assert_not_awaited()
        consumer.idempotency_service.release_claim.assert_awaited_once()

    async def test_missing_address_triggers_compensation(self):
        consumer = _make_consumer(resolve_cj_ids=(TEST_PID, TEST_VID))

        message = _make_order_confirmed_message(address=None)
        await consumer.handle_order_confirmed(message)

        consumer.cj_api_client.create_order_v2.assert_not_awaited()
        consumer._record_failed.assert_awaited_once()

    async def test_product_mapping_error_triggers_compensation(self):
        consumer = _make_consumer(
            resolve_cj_ids=ProductServiceError("product not found"),
        )

        await consumer.handle_order_confirmed(_make_order_confirmed_message())

        consumer.cj_api_client.create_order_v2.assert_not_awaited()
        consumer._record_failed.assert_awaited_once()

    async def test_payload_uses_validated_address_fields(self):
        consumer = _make_consumer(
            resolve_cj_ids=(TEST_PID, TEST_VID),
            create_order_response={
                "result": True,
                "code": 200,
                "data": {"orderId": TEST_CJ_ORDER_NUMBER},
            },
        )

        await consumer.handle_order_confirmed(_make_order_confirmed_message())

        payload = consumer.cj_api_client.create_order_v2.await_args.args[0]
        assert payload["orderNumber"] == str(TEST_ORDER_ID)
        assert payload["shippingCountryCode"] == "CA"
        assert payload["shippingZip"] == "T1T 1T1"
        assert payload["shippingCustomerName"] == "Test User"
        assert payload["products"] == [{"vid": TEST_VID, "quantity": 2}]

    async def test_invalid_address_fails_before_reaching_cj(self):
        """A bad address must compensate, never leave an unknown remote order."""
        consumer = _make_consumer(resolve_cj_ids=(TEST_PID, TEST_VID))
        message = _make_order_confirmed_message()
        message["address"]["postal_code"] = "not-a-postcode!"

        await consumer.handle_order_confirmed(message)

        consumer.cj_api_client.create_order_v2.assert_not_awaited()
        consumer.product_service_client.resolve_cj_ids.assert_not_awaited()
        consumer._record_failed.assert_awaited_once()
        assert "postal code" in consumer._record_failed.await_args.args[1]

    async def test_stock_out_fails_before_reaching_cj(self):
        """A CJ stock-out is a definitive failure the saga can refund."""
        consumer = _make_consumer(resolve_cj_ids=(TEST_PID, TEST_VID))
        consumer.inventory_verifier.verify_variant_stock = AsyncMock(
            return_value=SimpleNamespace(sufficient=False, buffered_available=0)
        )

        await consumer.handle_order_confirmed(_make_order_confirmed_message())

        consumer.cj_api_client.create_order_v2.assert_not_awaited()
        consumer._record_failed.assert_awaited_once()
        assert "Insufficient live CJ stock" in consumer._record_failed.await_args.args[1]

    async def test_cj_response_missing_order_id_raises(self):
        consumer = _make_consumer(
            resolve_cj_ids=(TEST_PID, TEST_VID),
            create_order_response={"result": True, "code": 200, "data": {}},
        )

        from shared.contracts.events import OrderConfirmedEvent
        event = OrderConfirmedEvent(**_make_order_confirmed_message())
        payload = await consumer._build_cj_order_payload(event)
        with pytest.raises(CJOrderCreationError):
            await consumer._submit_cj_order(event, payload)


class TestHandleOrderCancelled:
    def _cancel_message(self) -> dict:
        return {
            "event_id": str(uuid4()),
            "service": "order-service",
            "event_type": OrderEvents.ORDER_CANCELLED,
            "order_id": str(TEST_ORDER_ID),
            "user_id": str(TEST_USER_ID),
            "user_email": "test@example.com",
            "reason": "Payment failed",
        }

    async def test_deletes_a_created_cj_order(self):
        consumer = _make_consumer()
        consumer._get_attempt = AsyncMock(
            return_value=SimpleNamespace(
                status=CJOrderAttemptStatus.CREATED,
                cj_order_number=TEST_CJ_ORDER_NUMBER,
            )
        )
        consumer.cj_api_client.delete_order = AsyncMock(
            return_value={"result": True, "code": 200}
        )
        consumer._set_attempt_status = AsyncMock()

        await consumer.handle_order_cancelled(self._cancel_message())

        consumer.cj_api_client.delete_order.assert_awaited_once_with(TEST_CJ_ORDER_NUMBER)
        consumer._set_attempt_status.assert_awaited_once_with(
            TEST_ORDER_ID, CJOrderAttemptStatus.CANCELLED
        )

    async def test_shipped_order_is_flagged_instead_of_retried_forever(self):
        """CJ cannot un-ship a parcel, so retrying deleteOrder is pointless."""
        consumer = _make_consumer()
        consumer._get_attempt = AsyncMock(
            return_value=SimpleNamespace(
                status=CJOrderAttemptStatus.SHIPPED,
                cj_order_number=TEST_CJ_ORDER_NUMBER,
            )
        )
        consumer.cj_api_client.delete_order = AsyncMock()

        await consumer.handle_order_cancelled(self._cancel_message())

        consumer.cj_api_client.delete_order.assert_not_awaited()
        consumer._mark_reconciliation.assert_awaited_once()
        consumer.idempotency_service.release_claim.assert_not_awaited()
        assert (
            consumer.idempotency_service.mark_event_as_processed.await_args.args[3]
            == "cj_order_already_shipped"
        )

    async def test_paid_order_is_flagged_not_deleted(self):
        """CJ cannot delete a paid order; that money needs a human decision."""
        consumer = _make_consumer()
        consumer._get_attempt = AsyncMock(
            return_value=SimpleNamespace(
                status=CJOrderAttemptStatus.PAID,
                cj_order_number=TEST_CJ_ORDER_NUMBER,
            )
        )
        consumer.cj_api_client.delete_order = AsyncMock()

        await consumer.handle_order_cancelled(self._cancel_message())

        consumer.cj_api_client.delete_order.assert_not_awaited()
        consumer._mark_reconciliation.assert_awaited_once()
        consumer.idempotency_service.release_claim.assert_not_awaited()

    async def test_confirmed_unpaid_order_is_left_to_lapse_without_retrying(self):
        from service_layer.cj_api_client import CJDropshippingAPIError

        consumer = _make_consumer()
        consumer._get_attempt = AsyncMock(
            return_value=SimpleNamespace(
                status=CJOrderAttemptStatus.AWAITING_FUNDS,
                cj_order_number=TEST_CJ_ORDER_NUMBER,
            )
        )
        consumer.cj_api_client.delete_order = AsyncMock(
            side_effect=CJDropshippingAPIError("only CREATED or IN_CART orders can be deleted")
        )
        consumer.cj_api_client.get_order_detail = AsyncMock(
            return_value={"result": True, "code": 200, "data": {"orderStatus": "UNPAID"}}
        )
        consumer._set_attempt_status = AsyncMock()

        await consumer.handle_order_cancelled(self._cancel_message())

        consumer._set_attempt_status.assert_awaited_once_with(
            TEST_ORDER_ID, CJOrderAttemptStatus.CANCELLED
        )
        consumer._mark_reconciliation.assert_not_awaited()
        consumer.idempotency_service.release_claim.assert_not_awaited()

    async def test_network_error_while_deleting_is_retried(self):
        from service_layer.cj_api_client import CJDropshippingNetworkError

        consumer = _make_consumer()
        consumer._get_attempt = AsyncMock(
            return_value=SimpleNamespace(
                status=CJOrderAttemptStatus.CREATED,
                cj_order_number=TEST_CJ_ORDER_NUMBER,
            )
        )
        consumer.cj_api_client.delete_order = AsyncMock(
            side_effect=CJDropshippingNetworkError("timeout")
        )

        with pytest.raises(CJDropshippingNetworkError):
            await consumer.handle_order_cancelled(self._cancel_message())
        consumer.idempotency_service.release_claim.assert_awaited_once()

    async def test_order_without_a_cj_order_is_a_no_op(self):
        consumer = _make_consumer()
        consumer.cj_api_client.delete_order = AsyncMock()

        await consumer.handle_order_cancelled(self._cancel_message())

        consumer.cj_api_client.delete_order.assert_not_awaited()


class TestHandleImportFeedback:
    @pytest.mark.asyncio
    async def test_handle_import_feedback_success(self, monkeypatch) -> None:
        consumer = _make_consumer()
        fetch_id = uuid4()
        message = {
            "event_type": SupplierEvents.SUPPLIER_PRODUCT_IMPORT_COMPLETED,
            "supplier_id": "cjdropshipping",
            "fetch_id": str(fetch_id),
            "batch_id": str(uuid4()),
            "batch_number": 1,
            "total_batches": 1,
            "imported": 10,
            "updated": 2,
            "failed": 0,
        }

        mock_update = AsyncMock()
        monkeypatch.setattr(consumer, "_update_sync_state_on_feedback", mock_update)

        await consumer.handle_import_feedback_event(message)

        event = mock_update.await_args.kwargs["event"]
        assert event.fetch_id == fetch_id
        assert event.batch_number == 1

    @pytest.mark.asyncio
    async def test_handle_import_feedback_failure(self, monkeypatch) -> None:
        consumer = _make_consumer()
        fetch_id = uuid4()
        message = {
            "event_type": SupplierEvents.SUPPLIER_PRODUCT_IMPORT_FAILED,
            "supplier_id": "cjdropshipping",
            "fetch_id": str(fetch_id),
            "batch_id": str(uuid4()),
            "batch_number": 1,
            "total_batches": 1,
            "reason": "Invalid JSON",
        }

        mock_update = AsyncMock()
        monkeypatch.setattr(consumer, "_update_sync_state_on_failure", mock_update)

        await consumer.handle_import_feedback_event(message)

        event = mock_update.await_args.args[0]
        assert event.fetch_id == fetch_id
        assert event.reason == "Invalid JSON"

    @pytest.mark.asyncio
    async def test_completed_feedback_is_durably_idempotent(self, monkeypatch) -> None:
        consumer = _make_consumer()
        state = SimpleNamespace(
            acknowledged_batch_ids=[],
            processed_batches=0,
            total_batches=1,
            products_imported=0,
            products_updated=0,
            products_failed=0,
            error_message=None,
            status="awaiting_import",
            finished_at=None,
        )
        repository = MagicMock()
        repository.get_by_fetch_id_for_update = AsyncMock(return_value=state)
        repository.update = AsyncMock()
        monkeypatch.setattr(
            "event_consumer.supplier_event_consumer.SupplierSyncStateRepository",
            lambda session: repository,
        )

        @asynccontextmanager
        async def transaction():
            yield MagicMock()

        consumer.database.transaction = transaction
        event = SupplierProductImportCompletedEvent(
            supplier_id="cjdropshipping",
            fetch_id=uuid4(),
            batch_id=uuid4(),
            batch_number=1,
            total_batches=1,
            imported=2,
            updated=1,
            failed=1,
            errors=["bad product"],
        )

        await consumer._update_sync_state_on_feedback(event)
        await consumer._update_sync_state_on_feedback(event)

        assert state.processed_batches == 1
        assert state.products_imported == 2
        assert state.products_updated == 1
        assert state.products_failed == 1
        assert state.status == "completed_with_errors"
        assert state.acknowledged_batch_ids == [str(event.batch_id)]
