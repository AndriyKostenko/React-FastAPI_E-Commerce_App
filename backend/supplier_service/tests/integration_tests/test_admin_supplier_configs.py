"""
The one writable admin table: pause/resume a supplier's catalogue sync and
change its interval, against the real supplier test database. The admin guard
is the real one, fed by real gateway assertions (EphemeralSigningKeys).
"""

from collections.abc import AsyncGenerator
from logging import getLogger
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.dependencies import get_db_session
from models.base import Base
from models.supplier_config_models import SupplierConfig
from routes.admin_routes import admin_routes, supplier_config_admin_routes
from shared.managers.test_database_session_manager import TestDatabaseSessionManager
from shared.middleware.caller_assertion_middleware import CallerAssertionMiddleware
from shared.settings import get_settings
from shared.testing.signing_keys import ANONYMOUS, EphemeralSigningKeys

KEYS = EphemeralSigningKeys()
CONFIGS = "/api/v1/admin/supplier-configs"


@pytest.fixture
async def db() -> AsyncGenerator[TestDatabaseSessionManager, None]:
    manager = TestDatabaseSessionManager(
        database_url=get_settings().SUPPLIER_SERVICE_TEST_DATABASE_URL, logger=getLogger("test")
    )
    await manager.init_db(Base.metadata)
    yield manager
    await manager.truncate_all_tables(Base.metadata)
    await manager.close()


@pytest.fixture
async def client(db: TestDatabaseSessionManager) -> AsyncGenerator[AsyncClient, None]:
    app = FastAPI()
    # What every service app has (shared.app): the gateway's assertion becomes the caller.
    app.add_middleware(CallerAssertionMiddleware, logger=getLogger("test"))
    app.include_router(admin_routes, prefix="/api/v1")
    app.include_router(supplier_config_admin_routes, prefix="/api/v1")

    async def session() -> AsyncGenerator[AsyncSession, None]:
        async with db.transaction() as tx:
            yield tx

    app.dependency_overrides[get_db_session] = session
    KEYS.install_verifier(app)
    admin = KEYS.caller_auth(user_id=uuid4(), role=get_settings().SECRET_ROLE)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=admin) as http:
        yield http


async def _config(db: TestDatabaseSessionManager) -> str:
    async with db.transaction() as tx:
        config = SupplierConfig(supplier_id="cjdropshipping", name="CJ", provider_type="cjdropshipping",
                                is_active=True, sync_interval_minutes=60, config={})
        tx.add(config)
        await tx.flush()
        return str(config.id)


async def test_admin_pauses_a_supplier_and_changes_its_interval(client: AsyncClient, db: TestDatabaseSessionManager) -> None:
    config_id = await _config(db)

    response = await client.patch(f"{CONFIGS}/{config_id}", json={"is_active": False, "sync_interval_minutes": 120})
    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is False
    assert response.json()["sync_interval_minutes"] == 120

    # Stored, as the sync task reads it.
    async with db.transaction() as tx:
        stored = await tx.get(SupplierConfig, config_id)
        assert stored is not None and stored.is_active is False and stored.sync_interval_minutes == 120

    listed = await client.get(CONFIGS, params={"is_active": "false"})
    assert [row["id"] for row in listed.json()] == [config_id]


@pytest.mark.parametrize("body", [
    {"supplier_id": "someone-else"},       # identity is not editable
    {"provider_type": "other"},
    {"config": {"api_key": "x"}},          # nor the provider's own settings
    {"sync_interval_minutes": 1},          # a sync every minute would hammer CJ
])
async def test_only_the_sync_settings_can_change(client: AsyncClient, db: TestDatabaseSessionManager, body: dict[str, object]) -> None:
    config_id = await _config(db)
    response = await client.patch(f"{CONFIGS}/{config_id}", json=body)
    assert response.status_code == 422


async def test_unknown_config_is_404(client: AsyncClient, db: TestDatabaseSessionManager) -> None:
    response = await client.patch(f"{CONFIGS}/{uuid4()}", json={"is_active": False})
    assert response.status_code == 404


async def test_only_admins_change_supplier_configs(client: AsyncClient, db: TestDatabaseSessionManager) -> None:
    config_id = await _config(db)
    shopper = KEYS.caller_auth(user_id=uuid4(), role="user")
    assert (await client.patch(f"{CONFIGS}/{config_id}", json={"is_active": False}, auth=shopper)).status_code == 403
    assert (await client.patch(f"{CONFIGS}/{config_id}", json={"is_active": False}, auth=ANONYMOUS)).status_code == 401
    async with db.transaction() as tx:
        stored = await tx.get(SupplierConfig, config_id)
        assert stored is not None and stored.is_active is True
