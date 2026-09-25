"""Integration tests for the in-house production queue against a real database.

These cover the terminal path for a custom T-shirt: nothing else writes to a
``CustomProductionJob`` once the Saga queues it, so if these endpoints do not
move a job all the way to shipped, an order printed at home stays confirmed
forever and the customer never learns their parcel was posted.
"""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from config import settings
from database_layer.order_address_repository import OrderAddressRepository
from database_layer.order_fulfillment_repository import (
    CustomProductionJobRepository,
    OrderLineFulfillmentRepository,
)
from database_layer.order_item_repository import OrderItemRepository
from database_layer.order_repository import OrderRepository
from models.order_fulfillment_models import CustomProductionJob, OrderLineFulfillment
from models.outbox_models import OutboxEvent
from service_layer.order_address_service import OrderAddressService
from service_layer.order_fulfillment_status_service import OrderFulfillmentStatusService
from service_layer.order_item_service import OrderItemService
from service_layer.order_service import OrderService
from service_layer.outbox_event_service import OutboxEventService
from shared.contracts.artwork import GeneratedArtworkAsset, sign_artwork_asset
from shared.database_layer.outbox_repository import OutboxRepository
from shared.enums.event_enums import ArtworkEvents, OrderEvents, ProductionEvents
from shared.enums.status_enums import (
    LineFulfillmentStatus,
    OrderDeliveryStatus,
    OrderStatus,
    ProductionJobStatus,
)
from shared.managers.test_database_session_manager import TestDatabaseSessionManager
from tests.constants import TEST_API, TEST_EMAIL, TEST_PRODUCT_ID, TEST_USER_ID
from sqlalchemy import text


PRODUCTION_API = f"{TEST_API}/admin/production/jobs"


def _signed_asset() -> GeneratedArtworkAsset:
    """A manifest the pricing service will accept as issued by this backend."""
    unsigned = GeneratedArtworkAsset(
        key="generated-designs/2026/09/" + uuid4().hex + ".png",
        width_px=4096,
        height_px=4096,
        embedded_dpi=300,
        sha256="c" * 64,
        token="0" * 43,
    )
    return unsigned.model_copy(
        update={"token": sign_artwork_asset(unsigned, settings.ARTWORK_SIGNING_KEY)}
    )


def _custom_order_payload(asset: GeneratedArtworkAsset, **overrides) -> dict:
    base = {
        "user_id": str(TEST_USER_ID),
        "user_email": TEST_EMAIL,
        "currency": "cad",
        "payment_intent_id": str(uuid4()),
        "products": [
            {
                "id": str(uuid4()),
                "quantity": 1,
                "fulfillment_type": "custom",
                "customization": {
                    "design_asset": asset.model_dump(mode="json"),
                    "prompt": "Mountain sunrise",
                    "style": "Watercolor",
                    "size": "M",
                    "garment_color": "black",
                    "placement": "Center Chest",
                    "gender": "X",
                },
            }
        ],
        "address": {
            "street": "12 Workshop Lane",
            "city": "Test City",
            "province": "TC",
            "postal_code": "T2T 2T2",
            "name": "Test Buyer",
            "phone": "+15551234567",
        },
    }
    base.update(overrides)
    return base


def _catalog_line(product_id: UUID) -> dict:
    return {"id": str(product_id), "quantity": 1}


async def _confirm_payment(
    manager: TestDatabaseSessionManager,
    order_id: UUID,
    amount: Decimal,
    payment_intent_id: str,
) -> None:
    """Drive the Saga to CONFIRMED the way payment.authorized does.

    The production queue only exists downstream of a confirmed order, so the
    tests reach it through the real confirmation path rather than by inserting
    a job by hand.
    """
    async with manager.transaction() as session:
        order_repository = OrderRepository(session=session)
        service = OrderService(
            repository=order_repository,
            order_item_service=OrderItemService(
                repository=OrderItemRepository(session=session)
            ),
            order_address_service=OrderAddressService(
                repository=OrderAddressRepository(session=session)
            ),
            outbox_event_service=OutboxEventService(
                repository=OutboxRepository(session=session, model=OutboxEvent)
            ),
            fulfillment_status_service=OrderFulfillmentStatusService(
                order_repository=order_repository,
                fulfillment_repository=OrderLineFulfillmentRepository(session=session),
            ),
        )
        await service.record_payment_authorized(
            order_id,
            user_id=TEST_USER_ID,
            amount_cents=int((amount * 100).quantize(Decimal("1"))),
            currency="cad",
            payment_intent_id=payment_intent_id,
        )


async def _outbox_types(manager: TestDatabaseSessionManager) -> list[str]:
    async with manager.transaction() as session:
        rows = await session.execute(select(OutboxEvent.event_type))
        return list(rows.scalars().all())


@pytest.fixture
async def queued_job(
    integration_client: AsyncClient,
    test_database_session_manager: TestDatabaseSessionManager,
) -> dict:
    """A confirmed custom order with exactly one job waiting on the queue."""
    asset = _signed_asset()
    create = await integration_client.post(
        f"{TEST_API}/orders", json=_custom_order_payload(asset)
    )
    assert create.status_code == 201, create.text
    order = create.json()
    await _confirm_payment(
        test_database_session_manager,
        UUID(order["id"]),
        Decimal(str(order["amount"])),
        order["payment_intent_id"],
    )

    listing = await integration_client.get(PRODUCTION_API)
    assert listing.status_code == 200, listing.text
    jobs = listing.json()["items"]
    assert len(jobs) == 1
    return {"order": order, "job": jobs[0], "asset": asset}


class TestProductionQueueListing:
    async def test_confirming_a_custom_order_puts_a_job_on_the_queue(
        self, queued_job: dict
    ) -> None:
        job = queued_job["job"]
        assert job["status"] == ProductionJobStatus.QUEUED
        assert job["order_id"] == queued_job["order"]["id"]
        assert job["customer_email"] == TEST_EMAIL

    async def test_the_queue_carries_the_server_measured_print_specification(
        self, queued_job: dict
    ) -> None:
        specification = queued_job["job"]["print_specification"]
        assert specification["artwork_key"] == queued_job["asset"].key
        assert specification["placement"] == "Center Chest"
        # Measured server-side from the real print area, never sent by the client.
        assert specification["print_width_in"] == 12.0
        assert specification["print_height_in"] == 10.0
        assert specification["effective_dpi"] == 341.33

    async def test_status_filter_narrows_the_queue(
        self, integration_client: AsyncClient, queued_job: dict
    ) -> None:
        matching = await integration_client.get(
            PRODUCTION_API, params={"status": ProductionJobStatus.QUEUED.value}
        )
        other = await integration_client.get(
            PRODUCTION_API, params={"status": ProductionJobStatus.SHIPPED.value}
        )
        assert matching.json()["total"] == 1
        assert other.json()["total"] == 0

    async def test_a_catalog_only_order_puts_nothing_on_the_queue(
        self, integration_client: AsyncClient
    ) -> None:
        payload = _custom_order_payload(
            _signed_asset(), products=[_catalog_line(TEST_PRODUCT_ID)]
        )
        create = await integration_client.post(f"{TEST_API}/orders", json=payload)
        assert create.status_code == 201

        listing = await integration_client.get(PRODUCTION_API)
        assert listing.json()["total"] == 0


class TestProductionQueueArtworkAndPaperwork:
    async def test_artwork_download_resolves_the_stored_manifest(
        self, integration_client: AsyncClient, queued_job: dict, artwork_client_stub
    ) -> None:
        job_id = queued_job["job"]["id"]
        response = await integration_client.get(f"{PRODUCTION_API}/{job_id}/artwork")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["download_url"].endswith(".png")
        assert body["sha256"] == queued_job["asset"].sha256
        assert body["width_px"] == 4096
        # The manifest order_service stored is what was presented, unchanged.
        assert artwork_client_stub.requested_keys == [queued_job["asset"].key]

    async def test_no_database_connection_is_held_while_product_service_answers(
        self,
        integration_client: AsyncClient,
        queued_job: dict,
        artwork_client_stub,
        test_database_session_manager,
    ) -> None:
        # The job is read first; the request's transaction must be finished
        # before the remote call, or a pooled connection sits idle in
        # transaction for as long as product-service takes (up to 10s).
        held: list[int] = []

        async def count_idle_in_transaction() -> None:
            # Asked from a separate connection, so it counts only the others.
            async with test_database_session_manager.transaction() as session:
                result = await session.execute(text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND state = 'idle in transaction'"
                ))
                held.append(result.scalar_one())

        artwork_client_stub.during_call = count_idle_in_transaction

        response = await integration_client.get(f"{PRODUCTION_API}/{queued_job['job']['id']}/artwork")

        assert response.status_code == 200, response.text
        assert held == [0]

    async def test_packing_slip_carries_the_address_and_print_details(
        self, integration_client: AsyncClient, queued_job: dict
    ) -> None:
        job_id = queued_job["job"]["id"]
        response = await integration_client.get(
            f"{PRODUCTION_API}/{job_id}/packing-slip"
        )

        assert response.status_code == 200, response.text
        slip = response.json()
        assert slip["ship_to"]["street"] == "12 Workshop Lane"
        assert slip["ship_to"]["name"] == "Test Buyer"
        assert slip["customer_email"] == TEST_EMAIL
        assert slip["line"]["quantity"] == 1
        assert slip["print_specification"]["size"] == "M"


class TestProductionQueueLifecycle:
    async def test_the_full_path_ends_with_a_dispatched_order(
        self,
        integration_client: AsyncClient,
        queued_job: dict,
        test_database_session_manager: TestDatabaseSessionManager,
    ) -> None:
        job_id = queued_job["job"]["id"]
        order_id = queued_job["order"]["id"]

        started = await integration_client.post(
            f"{PRODUCTION_API}/{job_id}/start", json={"notes": "Blank pulled"}
        )
        printed = await integration_client.post(
            f"{PRODUCTION_API}/{job_id}/printed", json={}
        )
        shipped = await integration_client.post(
            f"{PRODUCTION_API}/{job_id}/ship",
            json={
                "tracking_number": "CP123456789CA",
                "carrier": "Canada Post",
                "tracking_url": "https://example.test/CP123456789CA",
            },
        )

        assert started.json()["status"] == ProductionJobStatus.IN_PRODUCTION
        assert printed.json()["status"] == ProductionJobStatus.PRINTED
        assert shipped.status_code == 200, shipped.text
        assert shipped.json()["status"] == ProductionJobStatus.SHIPPED
        assert shipped.json()["tracking_number"] == "CP123456789CA"

        # This is the whole point of the queue: without it the order stays
        # confirmed and pending forever.
        order = await integration_client.get(f"{TEST_API}/orders/{order_id}")
        assert order.json()["delivery_status"] == OrderDeliveryStatus.DISPATCHED

        delivered = await integration_client.post(f"{PRODUCTION_API}/{job_id}/delivered")
        assert delivered.json()["status"] == ProductionJobStatus.DELIVERED
        order = await integration_client.get(f"{TEST_API}/orders/{order_id}")
        assert order.json()["delivery_status"] == OrderDeliveryStatus.DELIVERED

    async def test_each_step_writes_the_event_that_notifies_the_customer(
        self,
        integration_client: AsyncClient,
        queued_job: dict,
        test_database_session_manager: TestDatabaseSessionManager,
    ) -> None:
        job_id = queued_job["job"]["id"]
        await integration_client.post(f"{PRODUCTION_API}/{job_id}/start", json={})
        await integration_client.post(f"{PRODUCTION_API}/{job_id}/printed", json={})
        await integration_client.post(
            f"{PRODUCTION_API}/{job_id}/ship",
            json={"tracking_number": "CP999999999CA"},
        )

        written = await _outbox_types(test_database_session_manager)
        assert ProductionEvents.PRODUCTION_JOB_STARTED in written
        assert ProductionEvents.PRODUCTION_JOB_PRINTED in written
        assert ProductionEvents.PRODUCTION_JOB_SHIPPED in written

    async def test_a_line_moves_with_its_job(
        self,
        integration_client: AsyncClient,
        queued_job: dict,
        test_database_session_manager: TestDatabaseSessionManager,
    ) -> None:
        job_id = queued_job["job"]["id"]
        await integration_client.post(f"{PRODUCTION_API}/{job_id}/start", json={})
        await integration_client.post(f"{PRODUCTION_API}/{job_id}/printed", json={})

        async with test_database_session_manager.transaction() as session:
            line = (
                await session.execute(select(OrderLineFulfillment))
            ).scalar_one()
        assert line.status == LineFulfillmentStatus.PRINTED

    async def test_shipping_before_printing_is_refused(
        self, integration_client: AsyncClient, queued_job: dict
    ) -> None:
        job_id = queued_job["job"]["id"]
        response = await integration_client.post(
            f"{PRODUCTION_API}/{job_id}/ship",
            json={"tracking_number": "CP000000000CA"},
        )
        assert response.status_code == 409

    async def test_a_held_job_resumes_at_the_step_it_reached(
        self, integration_client: AsyncClient, queued_job: dict
    ) -> None:
        job_id = queued_job["job"]["id"]
        await integration_client.post(f"{PRODUCTION_API}/{job_id}/start", json={})
        await integration_client.post(f"{PRODUCTION_API}/{job_id}/printed", json={})
        held = await integration_client.post(
            f"{PRODUCTION_API}/{job_id}/hold", json={"reason": "Out of mailers"}
        )
        resumed = await integration_client.post(f"{PRODUCTION_API}/{job_id}/resume")

        assert held.json()["status"] == ProductionJobStatus.ON_HOLD
        assert resumed.json()["status"] == ProductionJobStatus.PRINTED

    async def test_cancelling_a_printed_job_is_flagged_for_reconciliation(
        self, integration_client: AsyncClient, queued_job: dict
    ) -> None:
        job_id = queued_job["job"]["id"]
        await integration_client.post(f"{PRODUCTION_API}/{job_id}/start", json={})
        await integration_client.post(f"{PRODUCTION_API}/{job_id}/printed", json={})

        cancelled = await integration_client.post(
            f"{PRODUCTION_API}/{job_id}/cancel", json={"reason": "Print misaligned"}
        )
        assert cancelled.json()["status"] == ProductionJobStatus.CANCELLED
        # The blank and the ink are already spent; a human decides on refund.
        assert cancelled.json()["reconciliation_required"] is True


class TestOrderCancellationAgainstProduction:
    async def test_a_confirmed_order_retains_its_artwork(
        self, queued_job: dict, test_database_session_manager: TestDatabaseSessionManager
    ) -> None:
        written = await _outbox_types(test_database_session_manager)
        assert OrderEvents.ORDER_CONFIRMED in written
        assert ArtworkEvents.ARTWORK_RETAINED in written

    async def test_cancelling_before_printing_is_allowed_and_releases_artwork(
        self,
        integration_client: AsyncClient,
        queued_job: dict,
        test_database_session_manager: TestDatabaseSessionManager,
    ) -> None:
        order_id = queued_job["order"]["id"]
        response = await integration_client.patch(
            f"{TEST_API}/orders/{order_id}/cancel",
            json={"reason": "Customer changed their mind"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == OrderStatus.CANCELLED
        written = await _outbox_types(test_database_session_manager)
        assert ArtworkEvents.ARTWORK_RELEASED in written

        async with test_database_session_manager.transaction() as session:
            job = (await session.execute(select(CustomProductionJob))).scalar_one()
        assert job.status == ProductionJobStatus.CANCELLED
        assert job.reconciliation_required is False

    async def test_cancelling_a_printed_order_is_refused(
        self, integration_client: AsyncClient, queued_job: dict
    ) -> None:
        job_id = queued_job["job"]["id"]
        order_id = queued_job["order"]["id"]
        await integration_client.post(f"{PRODUCTION_API}/{job_id}/start", json={})
        await integration_client.post(f"{PRODUCTION_API}/{job_id}/printed", json={})

        response = await integration_client.patch(
            f"{TEST_API}/orders/{order_id}/cancel",
            json={"reason": "Too late"},
        )
        # A custom order never reaches delivery_status=delivered on its own, so
        # the old order-level guard never bound and printed goods stayed
        # cancellable-and-refundable.
        assert response.status_code == 409

    async def test_cancelling_a_shipped_order_is_refused(
        self, integration_client: AsyncClient, queued_job: dict
    ) -> None:
        job_id = queued_job["job"]["id"]
        order_id = queued_job["order"]["id"]
        await integration_client.post(f"{PRODUCTION_API}/{job_id}/start", json={})
        await integration_client.post(f"{PRODUCTION_API}/{job_id}/printed", json={})
        await integration_client.post(
            f"{PRODUCTION_API}/{job_id}/ship",
            json={"tracking_number": "CP111111111CA"},
        )

        response = await integration_client.patch(
            f"{TEST_API}/orders/{order_id}/cancel", json={"reason": "Too late"}
        )
        assert response.status_code == 409
