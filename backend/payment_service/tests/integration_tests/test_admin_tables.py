"""
The back office's read-only tables (shared.admin.admin_tables), exercised on
payment-service's disputes against the real test database: paging, newest
first, declared filters only, detail, field schema, and the admin guard.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from models.payment_models import PaymentDispute
from shared.managers.test_database_session_manager import TestDatabaseSessionManager
from shared.testing.signing_keys import ANONYMOUS
from tests.conftest import SIGNING_KEYS
from tests.constants import TEST_API

pytestmark = pytest.mark.asyncio(loop_scope="session")

DISPUTES = f"{TEST_API}/admin/disputes"


async def _seed(db: TestDatabaseSessionManager) -> list[UUID]:
    """Three disputes, one minute apart; returned newest first."""
    now = datetime.now(timezone.utc)
    rows = [
        PaymentDispute(stripe_dispute_id=f"dp_{i}", amount_cents=1_000 * (i + 1), currency="cad",
                       reason="fraudulent", status=status, date_created=now - timedelta(minutes=3 - i))
        for i, status in enumerate(["needs_response", "won", "needs_response"])
    ]
    async with db.transaction() as session:
        session.add_all(rows)
        await session.flush()
        ids = [row.id for row in rows]
    return list(reversed(ids))


async def test_lists_newest_first_and_pages(integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager) -> None:
    newest_first = await _seed(test_database_session_manager)

    everything = await integration_client.get(DISPUTES)
    assert everything.status_code == 200
    assert [UUID(row["id"]) for row in everything.json()] == newest_first

    second = await integration_client.get(DISPUTES, params={"limit": 1, "offset": 1})
    assert [UUID(row["id"]) for row in second.json()] == newest_first[1:2]


async def test_filters_only_on_declared_columns(integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager) -> None:
    await _seed(test_database_session_manager)

    won = await integration_client.get(DISPUTES, params={"status": "won"})
    assert [row["stripe_dispute_id"] for row in won.json()] == ["dp_1"]

    # amount_cents is not declared filterable: ignored, never turned into SQL.
    unfiltered = await integration_client.get(DISPUTES, params={"amount_cents": 1_000})
    assert len(unfiltered.json()) == 3

    malformed = await integration_client.get(DISPUTES, params={"payment_id": "not-a-uuid"})
    assert malformed.status_code == 422


async def test_page_size_is_capped(integration_client: AsyncClient) -> None:
    response = await integration_client.get(DISPUTES, params={"limit": 101})
    assert response.status_code == 422


async def test_detail_and_unknown_ids(integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager) -> None:
    newest = (await _seed(test_database_session_manager))[0]

    found = await integration_client.get(f"{DISPUTES}/{newest}")
    assert found.status_code == 200
    assert found.json()["stripe_dispute_id"] == "dp_2"

    assert (await integration_client.get(f"{DISPUTES}/{uuid4()}")).status_code == 404
    assert (await integration_client.get(f"{DISPUTES}/not-a-uuid")).status_code == 404


async def test_schema_describes_the_response_fields(integration_client: AsyncClient) -> None:
    response = await integration_client.get(f"{TEST_API}/admin/schema/disputes")
    assert response.status_code == 200
    fields = {field["path"]: field for field in response.json()["fields"]}
    assert fields["id"]["isId"] is True
    assert fields["amount_cents"]["type"] == "number"
    assert fields["evidence_due_by"]["type"] == "datetime"
    assert fields["payment_id"]["type"] == "string"


@pytest.mark.parametrize("path", [DISPUTES, f"{DISPUTES}/{uuid4()}", f"{TEST_API}/admin/schema/disputes"])
async def test_admins_only(integration_client: AsyncClient, path: str) -> None:
    shopper = SIGNING_KEYS.caller_auth(user_id=uuid4(), role="user")
    assert (await integration_client.get(path, auth=shopper)).status_code == 403
    assert (await integration_client.get(path, auth=ANONYMOUS)).status_code == 401
