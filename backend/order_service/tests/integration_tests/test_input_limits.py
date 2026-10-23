"""Over-long or oversized inputs are refused with a 422 before anything is priced or stored."""
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from contracts.limits import COUNT_MAX, IMAGES_MAX, LINES_MAX, TEXT_MAX_LENGTH
from enums.status_enums import OrderStatus, ProductionJobStatus
from infrastructure.managers.test_database_session_manager import TestDatabaseSessionManager
from models.order_models import Order
from tests.constants import TEST_API, TEST_PRODUCT_ID
from tests.integration_tests.test_order_routes import _order_payload


async def _orders_stored(manager: TestDatabaseSessionManager, payment_intent_id: str) -> int:
    async with manager.transaction() as session:
        return await session.scalar(
            select(func.count()).select_from(Order).where(Order.payment_intent_id == payment_intent_id)
        )


class TestAnOversizedOrderIsRefused:
    @pytest.mark.parametrize(
        ("address", "field"),
        [
            ({"street": "1" + " Yonge St" * 30}, "street"),
            ({"city": "T" * 101}, "city"),
            ({"name": "N" * 101}, "name"),
            ({"phone": "4" * 33}, "phone"),
        ],
        ids=["street", "city", "name", "phone"],
    )
    async def test_an_address_field_longer_than_an_account_address_allows(
        self,
        integration_client: AsyncClient,
        test_database_session_manager: TestDatabaseSessionManager,
        address: dict,
        field: str,
    ):
        payload = _order_payload()
        payload["address"] = {**payload["address"], **address}

        response = await integration_client.post(f"{TEST_API}/orders", json=payload)

        assert response.status_code == 422
        assert field in response.text
        assert await _orders_stored(test_database_session_manager, payload["payment_intent_id"]) == 0

    async def test_more_lines_than_a_cart_holds(
        self, integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager
    ):
        line = {"id": str(TEST_PRODUCT_ID), "price": "1.00", "quantity": 1}
        payload = _order_payload(products=[line] * (LINES_MAX + 1))

        response = await integration_client.post(f"{TEST_API}/orders", json=payload)

        assert response.status_code == 422
        assert await _orders_stored(test_database_session_manager, payload["payment_intent_id"]) == 0

    async def test_a_payment_intent_id_no_provider_issues(
        self, integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager
    ):
        payload = _order_payload(payment_intent_id="pi_" + "x" * 300)

        response = await integration_client.post(f"{TEST_API}/orders", json=payload)

        assert response.status_code == 422
        assert await _orders_stored(test_database_session_manager, payload["payment_intent_id"]) == 0


class TestOversizedRequestsAreRefused:
    async def test_a_cancellation_reason_longer_than_free_text_allows(self, integration_client: AsyncClient):
        created = await integration_client.post(f"{TEST_API}/orders", json=_order_payload())
        order_id = created.json()["id"]

        response = await integration_client.patch(
            f"{TEST_API}/orders/{order_id}/cancel", json={"reason": "r" * (TEXT_MAX_LENGTH + 1)}
        )

        assert response.status_code == 422
        # Still open: the refused request changed nothing.
        order = await integration_client.get(f"{TEST_API}/orders/{order_id}")
        assert order.json()["status"] != OrderStatus.CANCELLED

    async def test_a_production_queue_filter_naming_more_statuses_than_exist(
        self, integration_client: AsyncClient
    ):
        statuses = [("status", ProductionJobStatus.QUEUED.value)] * (len(ProductionJobStatus) + 1)

        response = await integration_client.get(f"{TEST_API}/admin/production/jobs", params=statuses)

        assert response.status_code == 422

    async def test_a_page_offset_past_any_real_table(self, integration_client: AsyncClient):
        response = await integration_client.get(
            f"{TEST_API}/admin/production/jobs", params={"offset": COUNT_MAX + 1}
        )

        assert response.status_code == 422

    async def test_a_return_photo_index_past_the_most_a_return_can_hold(self, integration_client: AsyncClient):
        response = await integration_client.get(f"{TEST_API}/admin/returns/{uuid4()}/photos/{IMAGES_MAX}")

        assert response.status_code == 422
