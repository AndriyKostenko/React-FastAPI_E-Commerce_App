"""
When does a request's transaction commit, relative to the response?

A table with a DEFERRED unique constraint fails only at COMMIT, which is the
point at which a deadlock, a serialization failure or a dropped connection
also surface. The client must never be told "created" for a write that then
failed to commit.
"""

from collections.abc import AsyncGenerator
from typing import Annotated, Literal

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.managers.test_database_session_manager import TestDatabaseSessionManager


pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
async def probe_table(test_database_session_manager: TestDatabaseSessionManager) -> AsyncGenerator[None, None]:
    async with test_database_session_manager.transaction() as session:
        await session.execute(text(
            "CREATE TABLE IF NOT EXISTS commit_probe ("
            " k int, CONSTRAINT commit_probe_k UNIQUE (k) DEFERRABLE INITIALLY DEFERRED)"
        ))
    yield
    async with test_database_session_manager.transaction() as session:
        await session.execute(text("DROP TABLE IF EXISTS commit_probe"))


def _app(manager: TestDatabaseSessionManager, scope: Literal["function"] | None) -> FastAPI:
    async def get_session() -> AsyncGenerator[AsyncSession, None]:
        async with manager.transaction() as session:
            yield session

    marker = Depends(get_session) if scope is None else Depends(get_session, scope=scope)
    app = FastAPI()

    @app.post("/probe", status_code=201)
    async def create(session: Annotated[AsyncSession, marker]) -> dict[str, str]:
        # Both inserts succeed now; the duplicate is only caught at COMMIT.
        await session.execute(text("INSERT INTO commit_probe (k) VALUES (1), (1)"))
        return {"status": "created"}

    return app


async def _post(app: FastAPI) -> int:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            return (await client.post("/probe")).status_code
        except Exception:  # the app blew up after the response had already gone out
            return -1


async def _rows(manager: TestDatabaseSessionManager) -> int:
    async with manager.transaction() as session:
        return (await session.execute(text("SELECT count(*) FROM commit_probe"))).scalar_one()


async def test_default_scope_reports_success_for_a_write_that_did_not_commit(
    probe_table: None, test_database_session_manager: TestDatabaseSessionManager
) -> None:
    status = await _post(_app(test_database_session_manager, scope=None))
    assert status == 201            # the client was told it worked...
    assert await _rows(test_database_session_manager) == 0   # ...and nothing was saved


async def test_function_scope_commits_before_answering(
    probe_table: None, test_database_session_manager: TestDatabaseSessionManager
) -> None:
    status = await _post(_app(test_database_session_manager, scope="function"))
    assert status == 500            # the failed commit is what the client hears
    assert await _rows(test_database_session_manager) == 0
