"""
The hourly stock refresh against real Postgres: two runs never overlap.

The advisory lock is the only thing keeping a slow refresh and the next
hour's from both walking the catalogue and doubling CJ traffic, so it is
checked on a real server rather than a fake.
"""

import asyncio
from logging import getLogger
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from service_layer.cj_api_client import CJDropshippingAPIError
from service_layer.cj_stock_refresh_service import CJStockRefreshService
from shared.contracts.supplier import SupplierStockKey
from shared.managers.test_database_session_manager import TestDatabaseSessionManager
from shared.settings import get_settings


@pytest.fixture
async def database():
    manager = TestDatabaseSessionManager(
        database_url=get_settings().SUPPLIER_SERVICE_TEST_DATABASE_URL, logger=getLogger("test")
    )
    yield manager
    await manager.close()


def _refresh(database, get_warehouse_stock) -> CJStockRefreshService:
    return CJStockRefreshService(
        settings=SimpleNamespace(CJ_DROPSHIPPING_INVENTORY_BUFFER=0, CJ_STOCK_REFRESH_BATCH_SIZE=100),
        database=database,
        provider=SimpleNamespace(get_warehouse_stock=get_warehouse_stock),
        product_client=SimpleNamespace(
            list_stock_keys=AsyncMock(return_value=[SupplierStockKey(supplier_pid="P", vids=["V"])])
        ),
        logger=getLogger("test"),
        sleep=AsyncMock(),
    )


async def test_a_second_refresh_while_one_runs_is_skipped_then_the_lock_frees(database) -> None:
    first_is_running = asyncio.Event()
    let_first_finish = asyncio.Event()

    async def slow_cj(_pid: str):
        first_is_running.set()
        await let_first_finish.wait()
        # Fails, so nothing is written to the outbox: only the lock is under test.
        raise CJDropshippingAPIError("stop here")

    first = asyncio.create_task(_refresh(database, slow_cj).refresh())
    await first_is_running.wait()

    second_cj = AsyncMock()
    second = await _refresh(database, second_cj).refresh()

    assert second.skipped_already_running is True
    second_cj.assert_not_awaited()

    let_first_finish.set()
    assert (await first).failed == 1

    # Released: the next hour's run goes ahead.
    third_cj = AsyncMock(side_effect=CJDropshippingAPIError("stop here"))
    third = await _refresh(database, third_cj).refresh()
    assert third.skipped_already_running is False
    third_cj.assert_awaited_once()
