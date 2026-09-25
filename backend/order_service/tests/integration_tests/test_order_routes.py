"""Integration tests for order endpoints using a real PostgreSQL test database."""
from datetime import datetime, timedelta, timezone
from logging import getLogger
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from models.order_fulfillment_models import OrderLineFulfillment
from models.order_item_models import OrderItem
from models.order_models import Order
from models.order_saga_models import OrderSagaState
from models.outbox_models import OutboxEvent
from shared.enums.event_enums import OrderEvents
from saga_timeout_worker import cancel_stalled_supplier_orders, expire_once
from config import settings
from shared.contracts.artwork import GeneratedArtworkAsset, sign_artwork_asset
from shared.managers.test_database_session_manager import TestDatabaseSessionManager
from shared.enums.status_enums import OrderStatus, OrderDeliveryStatus
from tests.constants import (
    TEST_USER_ID, TEST_EMAIL, TEST_AMOUNT, TEST_CURRENCY,
    TEST_PAYMENT_INTENT_ID, TEST_PRODUCT_ID, TEST_API,
)


def _order_payload(**overrides) -> dict:
    base = {
        "user_id": str(TEST_USER_ID),
        "user_email": TEST_EMAIL,
        "amount": TEST_AMOUNT,
        "currency": TEST_CURRENCY,
        "payment_intent_id": str(uuid4()),  # unique per test
        "products": [
            {
                "id": str(TEST_PRODUCT_ID),
                "name": "Test Widget",
                "price": "49.99",
                "quantity": 2,
            }
        ],
        "address": {
            "street": "123 Integration Ave",
            "city": "Test City",
            "province": "TC",
            "postal_code": "T2T 2T2",
        },
    }
    base.update(overrides)
    return base


class TestCreateOrderIntegration:
    async def test_create_order_returns_201(self, integration_client: AsyncClient):
        response = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        assert response.status_code == 201

    async def test_create_order_response_has_expected_fields(
        self, integration_client: AsyncClient
    ):
        response = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        data = response.json()
        assert "id" in data
        assert data["user_email"] == TEST_EMAIL
        assert data["status"] == OrderStatus.PENDING
        assert data["delivery_status"] == OrderDeliveryStatus.PENDING

    async def test_create_order_duplicate_payment_intent_returns_409(
        self, integration_client: AsyncClient
    ):
        fixed_intent = str(uuid4())
        payload = _order_payload(payment_intent_id=fixed_intent)

        await integration_client.post(f"{TEST_API}/orders", json=payload)
        response = await integration_client.post(f"{TEST_API}/orders", json=payload)

        assert response.status_code == 409

    async def test_custom_tshirt_persists_snapshot_without_inventory_gate(
        self,
        integration_client: AsyncClient,
        test_database_session_manager: TestDatabaseSessionManager,
    ):
        product_id = uuid4()
        unsigned_asset = GeneratedArtworkAsset(
            key="generated-designs/2026/08/" + "a" * 32 + ".png",
            width_px=4096,
            height_px=4096,
            embedded_dpi=300,
            sha256="b" * 64,
            token="0" * 43,
        )
        asset = unsigned_asset.model_copy(
            update={
                "token": sign_artwork_asset(
                    unsigned_asset, settings.ARTWORK_SIGNING_KEY
                )
            }
        )
        payload = _order_payload(
            products=[
                {
                    "id": str(product_id),
                    "price": "0.01",
                    "quantity": 2,
                    "fulfillment_type": "custom",
                    "customization": {
                        "design_asset": asset.model_dump(mode="json"),
                        "prompt": "Mountain sunrise",
                        "style": "Watercolor",
                        "size": "M",
                        "garment_color": "black",
                        "placement": "Full Back",
                        "gender": "X",
                    },
                }
            ]
        )

        response = await integration_client.post(f"{TEST_API}/orders", json=payload)

        assert response.status_code == 201
        order_id = UUID(response.json()["id"])
        async with test_database_session_manager.transaction() as session:
            saga = await session.get(OrderSagaState, order_id)
            fulfillment = (
                await session.execute(select(OrderLineFulfillment))
            ).scalar_one()
        assert saga.inventory_status == "not_required"
        assert fulfillment.fulfillment_type == "custom"
        assert fulfillment.customization["design_asset"]["key"] == asset.key
        assert fulfillment.customization["print_width_in"] == 15.0
        assert fulfillment.customization["print_height_in"] == 18.0
        assert fulfillment.customization["effective_dpi"] == 227.56

    async def test_cj_order_requires_complete_fulfillment_address(
        self, integration_client: AsyncClient, catalog_quote_stub
    ):
        # The catalog — not the client — decides a line is CJ-fulfilled.
        catalog_quote_stub.cj_product_ids.add(str(TEST_PRODUCT_ID))
        payload = _order_payload(
            products=[
                {
                    "id": str(TEST_PRODUCT_ID),
                    "variant_id": str(uuid4()),
                    "price": "20.00",
                    "quantity": 1,
                    "fulfillment_type": "cj",
                }
            ]
        )

        response = await integration_client.post(f"{TEST_API}/orders", json=payload)

        assert response.status_code == 422
        assert "country" in response.json()["detail"]


class TestGetOrdersIntegration:
    async def test_get_orders_returns_200(self, integration_client: AsyncClient):
        await integration_client.post(f"{TEST_API}/orders", json=_order_payload())
        response = await integration_client.get(f"{TEST_API}/orders")
        assert response.status_code == 200

    async def test_get_orders_returns_list(self, integration_client: AsyncClient):
        await integration_client.post(f"{TEST_API}/orders", json=_order_payload())
        response = await integration_client.get(f"{TEST_API}/orders")
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1

    async def test_get_orders_empty_returns_empty_list(self, integration_client: AsyncClient):
        # No orders created in this test — table was truncated before this fixture
        response = await integration_client.get(f"{TEST_API}/orders")
        assert response.status_code == 200
        assert response.json() == []


class TestGetOrderByIdIntegration:
    async def test_get_order_by_id_returns_200(self, integration_client: AsyncClient):
        create_resp = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        order_id = create_resp.json()["id"]

        response = await integration_client.get(f"{TEST_API}/orders/{order_id}")
        assert response.status_code == 200
        assert response.json()["id"] == order_id

    async def test_get_order_by_id_not_found_returns_404(
        self, integration_client: AsyncClient
    ):
        fake_id = str(uuid4())
        response = await integration_client.get(f"{TEST_API}/orders/{fake_id}")
        assert response.status_code == 404


class TestGetOrdersByUserIdIntegration:
    async def test_get_orders_by_user_id_returns_200(
        self, integration_client: AsyncClient
    ):
        await integration_client.post(f"{TEST_API}/orders", json=_order_payload())
        response = await integration_client.get(
            f"{TEST_API}/orders/user/{TEST_USER_ID}"
        )
        assert response.status_code == 200
        data = response.json()
        assert all(o["user_id"] == str(TEST_USER_ID) for o in data)


class TestUpdateOrderIntegration:
    async def test_update_order_delivery_status(self, integration_client: AsyncClient):
        create_resp = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        order_id = create_resp.json()["id"]

        response = await integration_client.patch(
            f"{TEST_API}/orders/{order_id}",
            json={"delivery_status": OrderDeliveryStatus.DELIVERED},
        )
        assert response.status_code == 200
        assert response.json()["delivery_status"] == OrderDeliveryStatus.DELIVERED

    async def test_update_order_cannot_force_confirmed(
        self, integration_client: AsyncClient
    ):
        create_resp = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        order_id = create_resp.json()["id"]

        response = await integration_client.patch(
            f"{TEST_API}/orders/{order_id}",
            json={"status": OrderStatus.CONFIRMED},
        )
        assert response.status_code == 200
        assert response.json()["status"] == OrderStatus.PENDING


class TestCancelOrderIntegration:
    async def test_cancel_pending_order_returns_200(
        self, integration_client: AsyncClient
    ):
        create_resp = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        order_id = create_resp.json()["id"]

        response = await integration_client.patch(
            f"{TEST_API}/orders/{order_id}/cancel",
            json={"reason": "Integration test cancellation"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == OrderStatus.CANCELLED

    async def test_cancel_already_cancelled_order_returns_409(
        self, integration_client: AsyncClient
    ):
        create_resp = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        order_id = create_resp.json()["id"]

        await integration_client.patch(
            f"{TEST_API}/orders/{order_id}/cancel",
            json={"reason": "First cancellation"},
        )
        response = await integration_client.patch(
            f"{TEST_API}/orders/{order_id}/cancel",
            json={"reason": "Second cancellation"},
        )
        assert response.status_code == 409

    async def test_timeout_worker_cancels_abandoned_pending_saga(
        self,
        integration_client: AsyncClient,
        test_database_session_manager: TestDatabaseSessionManager,
    ):
        create_response = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        order_id = UUID(create_response.json()["id"])
        async with test_database_session_manager.transaction() as session:
            saga = await session.get(OrderSagaState, order_id)
            saga.date_created = datetime.now(timezone.utc) - timedelta(hours=1)

        expired = await expire_once(
            SimpleNamespace(
                database=test_database_session_manager,
                settings=SimpleNamespace(ORDER_SAGA_TIMEOUT_SECONDS=60),
            )
        )

        response = await integration_client.get(f"{TEST_API}/orders/{order_id}")
        assert expired == 1
        assert response.json()["status"] == OrderStatus.CANCELLED


class TestStalledSupplierOrders:
    """
    A confirmed order whose CJ part never got going is cancelled after
    ORDER_SUPPLIER_STALL_HOURS instead of waiting for the card hold to lapse.
    """

    STALL_HOURS = 24

    async def _confirmed_cj_order(
        self,
        client: AsyncClient,
        stub,
        db: TestDatabaseSessionManager,
        *,
        confirmed_hours_ago: float,
        line_status: str = "pending",
    ) -> UUID:
        stub.cj_product_ids.add(str(TEST_PRODUCT_ID))
        response = await client.post(
            f"{TEST_API}/orders",
            json=_order_payload(
                products=[{
                    "id": str(TEST_PRODUCT_ID),
                    "variant_id": str(uuid4()),
                    "price": "20.00",
                    "quantity": 1,
                    "fulfillment_type": "cj",
                }],
                address={
                    "street": "1 Main St", "city": "Calgary", "province": "AB",
                    "postal_code": "T1T 1T1", "country": "Canada", "country_code": "CA",
                    "name": "Test Buyer", "phone": "4035550100",
                },
            ),
        )
        assert response.status_code == 201, response.text
        order_id = UUID(response.json()["id"])
        # The state payment.authorized + inventory.reserved leave behind.
        async with db.transaction() as session:
            saga = await session.get(OrderSagaState, order_id)
            saga.payment_status = "authorized"
            saga.inventory_status = "reserved"
            saga.fulfillment_status = "ready"
            saga.confirmed_at = datetime.now(timezone.utc) - timedelta(hours=confirmed_hours_ago)
            order = await session.get(Order, order_id)
            order.status = OrderStatus.CONFIRMED
            lines = (await session.execute(
                select(OrderLineFulfillment)
                .join(OrderItem, OrderItem.id == OrderLineFulfillment.order_item_id)
                .where(OrderItem.order_id == order_id)
            )).scalars().all()
            assert lines and all(line.fulfillment_type == "cj" for line in lines)
            for line in lines:
                line.status = line_status
        return order_id

    def _resources(self, db: TestDatabaseSessionManager) -> SimpleNamespace:
        return SimpleNamespace(
            database=db,
            settings=SimpleNamespace(ORDER_SUPPLIER_STALL_HOURS=self.STALL_HOURS),
            logger=getLogger("test.stalled-orders"),
        )

    async def test_an_order_cj_never_took_on_is_cancelled(
        self, integration_client: AsyncClient, catalog_quote_stub, test_database_session_manager
    ):
        order_id = await self._confirmed_cj_order(
            integration_client, catalog_quote_stub, test_database_session_manager, confirmed_hours_ago=25
        )

        cancelled = await cancel_stalled_supplier_orders(self._resources(test_database_session_manager))

        assert cancelled == 1
        order = (await integration_client.get(f"{TEST_API}/orders/{order_id}")).json()
        assert order["status"] == OrderStatus.CANCELLED
        async with test_database_session_manager.transaction() as session:
            saga = await session.get(OrderSagaState, order_id)
            # order.cancelled is what makes payment-service void the hold.
            events = (await session.execute(
                select(OutboxEvent.event_type).where(OutboxEvent.payload["order_id"].as_string() == str(order_id))
            )).scalars().all()
        assert "CJ did not accept" in saga.cancellation_reason
        assert OrderEvents.ORDER_CANCELLED in events

    @pytest.mark.parametrize(
        ("confirmed_hours_ago", "line_status", "why"),
        [
            (2, "pending", "still inside the window"),
            (25, "submitted", "CJ was paid; capture is under way"),
        ],
    )
    async def test_orders_that_are_not_stalled_are_left_alone(
        self,
        integration_client: AsyncClient,
        catalog_quote_stub,
        test_database_session_manager,
        confirmed_hours_ago: float,
        line_status: str,
        why: str,
    ):
        order_id = await self._confirmed_cj_order(
            integration_client,
            catalog_quote_stub,
            test_database_session_manager,
            confirmed_hours_ago=confirmed_hours_ago,
            line_status=line_status,
        )

        cancelled = await cancel_stalled_supplier_orders(self._resources(test_database_session_manager))

        assert cancelled == 0, why
        order = (await integration_client.get(f"{TEST_API}/orders/{order_id}")).json()
        assert order["status"] == OrderStatus.CONFIRMED, why


class TestDeleteOrderIntegration:
    async def test_delete_order_returns_204(self, integration_client: AsyncClient):
        create_resp = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        order_id = create_resp.json()["id"]

        response = await integration_client.delete(f"{TEST_API}/orders/{order_id}")
        assert response.status_code == 204

    async def test_deleted_order_is_not_found(self, integration_client: AsyncClient):
        create_resp = await integration_client.post(
            f"{TEST_API}/orders", json=_order_payload()
        )
        order_id = create_resp.json()["id"]

        await integration_client.delete(f"{TEST_API}/orders/{order_id}")
        response = await integration_client.get(f"{TEST_API}/orders/{order_id}")
        assert response.status_code == 404
