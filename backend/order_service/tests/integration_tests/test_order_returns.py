"""
Customer returns through the API, against the real order test database.

The confirmed order comes from the production-queue fixture: a real custom
order confirmed through the payment path. A test that needs a catalog or CJ
line re-labels the line's fulfilment type, and delivery is recorded the way
the fulfilment channels record it. Photos go through the app's own storage:
the local S3 server's private test bucket under ``dev.sh test``.
"""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from database_layer.order_fulfillment_repository import OrderLineFulfillmentRepository
from database_layer.order_repository import OrderRepository
from httpx import AsyncClient
from main import app
from models.order_refund_models import OrderRefund
from models.outbox_models import OutboxEvent
from service_layer.order_fulfillment_status_service import OrderFulfillmentStatusService
from shared.enums.event_enums import OrderEvents, PaymentCommands
from shared.enums.status_enums import LineFulfillmentStatus
from shared.managers.test_database_session_manager import TestDatabaseSessionManager
from shared.testing.signing_keys import ANONYMOUS
from sqlalchemy import select

from tests.conftest import SIGNING_KEYS
from tests.constants import TEST_API, TEST_USER_ID
from tests.integration_tests.test_production_routes import (
    queued_job,  # noqa: F401 (fixture)
)

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
OWNER = SIGNING_KEYS.caller_auth(user_id=TEST_USER_ID)
STRANGER = SIGNING_KEYS.caller_auth(user_id=uuid4())


# ---------------------------------------------------------------- helpers


def _returns_url(order_id: str) -> str:
    return f"{TEST_API}/orders/{order_id}/returns"


async def _line(db: TestDatabaseSessionManager, order_id: str) -> tuple[str, int]:
    async with db.transaction() as session:
        order = await OrderRepository(session).get_with_fulfillment(UUID(order_id))
        return str(order.items[0].id), order.items[0].quantity


async def _deliver(
    db: TestDatabaseSessionManager,
    order_id: str,
    *,
    fulfillment_type: str | None = None,
    days_ago: int = 0,
) -> None:
    """Deliver every line as a channel would, optionally re-labelled and back-dated."""
    if fulfillment_type:
        async with db.transaction() as session:
            for item in (await OrderRepository(session).get_with_fulfillment(UUID(order_id))).items:
                item.fulfillment.fulfillment_type = fulfillment_type
    async with db.transaction() as session:
        order = await OrderRepository(session).get_with_fulfillment(UUID(order_id))
        await OrderFulfillmentStatusService(
            OrderRepository(session), OrderLineFulfillmentRepository(session)
        ).mark_lines(order, LineFulfillmentStatus.DELIVERED)
    if days_ago:
        async with db.transaction() as session:
            for item in (
                await OrderRepository(session).get_with_fulfillment(UUID(order_id))
            ).items:
                item.fulfillment.delivered_at = datetime.now(UTC) - timedelta(
                    days=days_ago
                )


async def _ask(
    client: AsyncClient,
    order_id: str,
    lines: list[tuple[str, int]],
    reason: str,
    photos: list[bytes] | None = None,
    auth=OWNER,
):
    body = {
        "lines": [
            {"order_item_id": item_id, "quantity": quantity}
            for item_id, quantity in lines
        ],
        "reason": reason,
        "description": "Details of what went wrong",
    }
    files = [
        ("photos", (f"p{i}.jpg", content, "image/jpeg"))
        for i, content in enumerate(photos or [])
    ]
    return await client.post(
        _returns_url(order_id),
        data={"request": json.dumps(body)},
        files=files or None,
        auth=auth,
    )


async def _refunds(db: TestDatabaseSessionManager) -> list[OrderRefund]:
    async with db.transaction() as session:
        return list((await session.execute(select(OrderRefund))).scalars().all())


async def _events(db: TestDatabaseSessionManager, event_type: str) -> list[dict]:
    async with db.transaction() as session:
        rows = await session.execute(
            select(OutboxEvent.payload).where(OutboxEvent.event_type == event_type)
        )
        return list(rows.scalars().all())


def _admin(return_id: str, action: str) -> str:
    return f"{TEST_API}/admin/returns/{return_id}/{action}"


# ------------------------------------------------------------ delivery clock


async def test_delivering_a_line_starts_its_return_clock(
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    before = datetime.now(UTC)
    await _deliver(test_database_session_manager, order_id)
    async with test_database_session_manager.transaction() as session:
        order = await OrderRepository(session).get_with_fulfillment(UUID(order_id))
        assert order.items[0].fulfillment.delivered_at >= before


# ------------------------------------------------------------- eligibility


async def test_an_undelivered_line_cannot_be_returned_yet(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, _ = await _line(test_database_session_manager, order_id)

    eligibility = (
        await integration_client.get(
            f"{_returns_url(order_id)}/eligibility", auth=OWNER
        )
    ).json()
    response = await _ask(
        integration_client, order_id, [(item_id, 1)], "defective", [JPEG]
    )

    assert eligibility["lines"][0]["returnable_quantity"] == 0
    assert (
        eligibility["lines"][0]["unavailable_reason"] == "it has not been delivered yet"
    )
    assert response.status_code == 422


async def test_eligibility_offers_a_custom_print_only_the_sellers_faults(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    _, quantity = await _line(test_database_session_manager, order_id)
    await _deliver(test_database_session_manager, order_id)

    body = (
        await integration_client.get(
            f"{_returns_url(order_id)}/eligibility", auth=OWNER
        )
    ).json()

    line = body["lines"][0]
    assert (
        line["returnable_quantity"] == quantity and line["unavailable_reason"] is None
    )
    assert set(line["allowed_reasons"]) == {
        "defective",
        "damaged",
        "wrong_item",
        "misprint",
    }
    assert body["window_days"] == 30


async def test_the_window_closes_thirty_days_after_delivery(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, _ = await _line(test_database_session_manager, order_id)
    await _deliver(test_database_session_manager, order_id, days_ago=31)

    response = await _ask(
        integration_client, order_id, [(item_id, 1)], "defective", [JPEG]
    )

    assert response.status_code == 422
    assert "window has closed" in response.text


# ---------------------------------------------------------- who may ask


@pytest.mark.parametrize(
    ("caller", "expected"),
    [(ANONYMOUS, 401), (STRANGER, 403)],
    ids=["anonymous", "stranger"],
)
async def test_only_the_buyer_may_ask(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,
    caller,
    expected: int,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, _ = await _line(test_database_session_manager, order_id)
    await _deliver(test_database_session_manager, order_id)

    response = await _ask(
        integration_client, order_id, [(item_id, 1)], "defective", [JPEG], auth=caller
    )

    assert response.status_code == expected
    assert (
        await _events(test_database_session_manager, OrderEvents.RETURN_REQUESTED) == []
    )


async def test_a_customer_cannot_decide_a_return(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, _ = await _line(test_database_session_manager, order_id)
    await _deliver(test_database_session_manager, order_id)
    created = (
        await _ask(integration_client, order_id, [(item_id, 1)], "defective", [JPEG])
    ).json()

    response = await integration_client.post(
        _admin(created["id"], "approve"), json={}, auth=OWNER
    )

    assert response.status_code == 403
    assert await _refunds(test_database_session_manager) == []


# ------------------------------------------------------------ what is accepted


async def test_a_custom_print_is_not_returned_for_a_change_of_mind(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, _ = await _line(test_database_session_manager, order_id)
    await _deliver(test_database_session_manager, order_id)

    response = await _ask(integration_client, order_id, [(item_id, 1)], "changed_mind")

    assert response.status_code == 422
    assert "made to order" in response.text


async def test_the_sellers_fault_needs_a_real_photo(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, _ = await _line(test_database_session_manager, order_id)
    await _deliver(test_database_session_manager, order_id)

    without = await _ask(integration_client, order_id, [(item_id, 1)], "defective")
    fake = await _ask(
        integration_client,
        order_id,
        [(item_id, 1)],
        "defective",
        [b"<html>not an image</html>"],
    )

    assert without.status_code == 422 and "photo" in without.text
    assert fake.status_code == 422 and "not a JPEG, PNG or WebP" in fake.text


async def test_a_defective_print_is_requested_with_its_photo_and_the_admin_is_alerted(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, _ = await _line(test_database_session_manager, order_id)
    await _deliver(test_database_session_manager, order_id)

    response = await _ask(
        integration_client, order_id, [(item_id, 1)], "misprint", [PNG]
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "requested" and body["fault"] == "seller"
    assert body["lines"] == [
        {
            "order_item_id": item_id,
            "quantity": 1,
            "ships_back": False,
            "refunded": False,
        }
    ]
    assert body["photos"] == [
        {"index": 0, "content_type": "image/png", "size": len(PNG)}
    ]

    photo = await integration_client.get(
        f"{TEST_API}/admin/returns/{body['id']}/photos/0"
    )
    assert photo.status_code == 200 and photo.content == PNG
    assert photo.headers["content-type"] == "image/png"

    [event] = await _events(test_database_session_manager, OrderEvents.RETURN_REQUESTED)
    assert event["return_id"] == body["id"] and event["photo_count"] == 1
    # Nothing is paid out until an admin decides.
    assert await _refunds(test_database_session_manager) == []


# ---------------------------------------------------------- once per unit


async def test_each_unit_is_returned_at_most_once(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, quantity = await _line(test_database_session_manager, order_id)
    await _deliver(test_database_session_manager, order_id)

    first = await _ask(
        integration_client, order_id, [(item_id, quantity)], "defective", [JPEG]
    )
    again = await _ask(integration_client, order_id, [(item_id, 1)], "damaged", [JPEG])

    assert first.status_code == 201
    assert again.status_code == 422
    assert "already been returned" in again.text


async def test_withdrawing_a_return_frees_its_units(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, quantity = await _line(test_database_session_manager, order_id)
    await _deliver(test_database_session_manager, order_id)
    created = (
        await _ask(
            integration_client, order_id, [(item_id, quantity)], "defective", [JPEG]
        )
    ).json()

    cancelled = await integration_client.post(
        f"{_returns_url(order_id)}/{created['id']}/cancel", auth=OWNER
    )
    again = await _ask(
        integration_client, order_id, [(item_id, quantity)], "defective", [JPEG]
    )

    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert again.status_code == 201


async def test_an_approved_return_can_no_longer_be_withdrawn(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, _ = await _line(test_database_session_manager, order_id)
    await _deliver(test_database_session_manager, order_id, fulfillment_type="catalog")
    created = (
        await _ask(integration_client, order_id, [(item_id, 1)], "changed_mind")
    ).json()
    await integration_client.post(_admin(created["id"], "approve"), json={})

    response = await integration_client.post(
        f"{_returns_url(order_id)}/{created['id']}/cancel", auth=OWNER
    )

    assert response.status_code == 409


# --------------------------------------------------------- deciding + money


async def test_approving_a_returnless_defect_refunds_it_with_the_shipping(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, _ = await _line(test_database_session_manager, order_id)
    await _deliver(test_database_session_manager, order_id)
    created = (
        await _ask(integration_client, order_id, [(item_id, 1)], "defective", [JPEG])
    ).json()

    response = await integration_client.post(
        _admin(created["id"], "approve"), json={"note": "clear misprint"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    # Nothing has to come back, so the return is done the moment it is approved.
    assert body["status"] == "completed" and body["lines"][0]["refunded"] is True
    [refund] = await _refunds(test_database_session_manager)
    assert refund.return_request_id == UUID(created["id"])
    assert refund.lines[0]["quantity"] == 1
    # Our fault: the order's shipping goes back too (when it had any).
    order = queued_job["order"]
    assert refund.includes_shipping is (float(order.get("shipping_amount") or 0) > 0)
    assert (
        len(
            await _events(
                test_database_session_manager, PaymentCommands.REFUND_REQUESTED
            )
        )
        == 1
    )
    [approved] = await _events(
        test_database_session_manager, OrderEvents.RETURN_APPROVED
    )
    assert (
        approved["admin_note"] == "clear misprint"
        and approved["return_address"] is None
    )


async def test_a_change_of_mind_is_refunded_only_when_the_parcel_arrives_and_without_shipping(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, _ = await _line(test_database_session_manager, order_id)
    await _deliver(test_database_session_manager, order_id, fulfillment_type="catalog")
    created = (
        await _ask(integration_client, order_id, [(item_id, 1)], "does_not_fit")
    ).json()
    assert created["lines"][0]["ships_back"] is True

    approved = await integration_client.post(_admin(created["id"], "approve"), json={})
    assert approved.json()["status"] == "approved"
    assert await _refunds(test_database_session_manager) == []

    received = await integration_client.post(
        _admin(created["id"], "receive"), json={"note": "unworn"}
    )

    assert received.status_code == 200, received.text
    assert (
        received.json()["status"] == "completed"
        and received.json()["received_at"] is not None
    )
    [refund] = await _refunds(test_database_session_manager)
    assert refund.includes_shipping is False


async def test_a_dropshipped_defect_stays_with_the_customer_but_a_change_of_mind_comes_back(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, quantity = await _line(test_database_session_manager, order_id)
    await _deliver(test_database_session_manager, order_id, fulfillment_type="cj")

    defect = await _ask(integration_client, order_id, [(item_id, 1)], "damaged", [JPEG])
    assert defect.json()["lines"][0]["ships_back"] is False
    await integration_client.post(
        f"{_returns_url(order_id)}/{defect.json()['id']}/cancel", auth=OWNER
    )

    change = await _ask(
        integration_client, order_id, [(item_id, quantity)], "changed_mind"
    )
    assert change.status_code == 201 and change.json()["lines"][0]["ships_back"] is True


async def test_rejecting_an_approved_return_frees_the_units_it_never_refunded(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, quantity = await _line(test_database_session_manager, order_id)
    await _deliver(test_database_session_manager, order_id, fulfillment_type="catalog")
    created = (
        await _ask(integration_client, order_id, [(item_id, quantity)], "changed_mind")
    ).json()
    await integration_client.post(_admin(created["id"], "approve"), json={})

    rejected = await integration_client.post(
        _admin(created["id"], "reject"), json={"note": "never arrived"}
    )
    again = await _ask(
        integration_client, order_id, [(item_id, quantity)], "changed_mind"
    )

    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    assert again.status_code == 201
    assert await _refunds(test_database_session_manager) == []
    [event] = await _events(test_database_session_manager, OrderEvents.RETURN_REJECTED)
    assert "never arrived" in event["admin_note"]


async def test_a_unit_refunded_by_an_admin_meanwhile_is_never_paid_twice(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    """An admin refund made while a return is open must make the return's approval fail, not pay again."""
    order_id = queued_job["order"]["id"]
    item_id, quantity = await _line(test_database_session_manager, order_id)
    await _deliver(test_database_session_manager, order_id)
    created = (
        await _ask(
            integration_client, order_id, [(item_id, quantity)], "defective", [JPEG]
        )
    ).json()
    admin_refund = await integration_client.post(
        f"{TEST_API}/admin/orders/{order_id}/refunds",
        json={
            "lines": [{"order_item_id": item_id, "quantity": quantity}],
            "reason": "goodwill",
        },
    )
    assert admin_refund.status_code == 201

    response = await integration_client.post(_admin(created["id"], "approve"), json={})

    assert response.status_code == 422
    assert len(await _refunds(test_database_session_manager)) == 1
    listing = (await integration_client.get(_returns_url(order_id), auth=OWNER)).json()
    assert listing[0]["status"] == "requested"


async def test_a_return_is_decided_only_once(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, _ = await _line(test_database_session_manager, order_id)
    await _deliver(test_database_session_manager, order_id)
    created = (
        await _ask(integration_client, order_id, [(item_id, 1)], "defective", [JPEG])
    ).json()

    first = await integration_client.post(_admin(created["id"], "approve"), json={})
    second = await integration_client.post(_admin(created["id"], "approve"), json={})
    reject = await integration_client.post(
        _admin(created["id"], "reject"), json={"note": "changed my mind"}
    )

    assert first.status_code == 200
    assert second.status_code == 409 and reject.status_code == 409
    assert len(await _refunds(test_database_session_manager)) == 1


async def test_the_admin_queue_lists_requests_oldest_first(
    integration_client: AsyncClient,
    queued_job: dict,
    test_database_session_manager,  # noqa: F811
) -> None:
    order_id = queued_job["order"]["id"]
    item_id, _ = await _line(test_database_session_manager, order_id)
    await _deliver(test_database_session_manager, order_id)
    created = (
        await _ask(integration_client, order_id, [(item_id, 1)], "defective", [JPEG])
    ).json()

    requested = await integration_client.get(
        f"{TEST_API}/admin/returns", params={"status": "requested"}
    )
    completed = await integration_client.get(
        f"{TEST_API}/admin/returns", params={"status": "completed"}
    )

    assert [r["id"] for r in requested.json()] == [created["id"]]
    assert completed.json() == []
