"""
The hourly CJ stock refresh: which products it asks about, what it sends,
what a failure leaves alone. CJ and product-service are fakes; the outbox
write is captured.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from logging import getLogger
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import service_layer.cj_stock_refresh_service as refresh_module
from service_layer.cj_api_client import CJDropshippingAPIError
from service_layer.cj_stock_refresh_service import CJStockRefreshService
from service_layer.supplier_provider import WarehouseStock
from shared.contracts.supplier import SupplierStockKey
from shared.enums.event_enums import SupplierEvents

T0 = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


class _LockConnection:
    def __init__(self, acquired: bool) -> None:
        self.acquired = acquired
        self.statements: list[str] = []

    async def scalar(self, statement, _params):
        self.statements.append(str(statement))
        return self.acquired

    async def execute(self, statement, _params):
        self.statements.append(str(statement))

    async def commit(self) -> None: ...


class _Database:
    def __init__(self, lock_acquired: bool = True) -> None:
        self.lock = _LockConnection(lock_acquired)
        self.async_engine = SimpleNamespace(connect=self._connect)

    @asynccontextmanager
    async def _connect(self):
        yield self.lock

    @asynccontextmanager
    async def transaction(self):
        yield MagicMock()


@pytest.fixture
def sent(monkeypatch) -> list[tuple[str, object]]:
    """Every event written to the outbox, in order."""
    events: list[tuple[str, object]] = []

    class _Outbox:
        def __init__(self, _repository) -> None: ...

        async def add_outbox_event(self, event_type, payload):
            events.append((event_type, payload))

    monkeypatch.setattr(refresh_module, "OutboxEventService", _Outbox)
    monkeypatch.setattr(refresh_module, "OutboxRepository", lambda **_kwargs: None)
    return events


def _service(
    keys: list[SupplierStockKey],
    stock: dict[str, WarehouseStock | Exception],
    *,
    buffer: int = 0,
    batch_size: int = 100,
    database: _Database | None = None,
) -> tuple[CJStockRefreshService, SimpleNamespace, AsyncMock]:
    async def get_warehouse_stock(pid: str) -> WarehouseStock:
        result = stock[pid]
        if isinstance(result, Exception):
            raise result
        return result

    provider = SimpleNamespace(get_warehouse_stock=AsyncMock(side_effect=get_warehouse_stock))
    sleep = AsyncMock()
    clock = iter(T0 + timedelta(seconds=i) for i in range(1000))
    service = CJStockRefreshService(
        settings=SimpleNamespace(CJ_DROPSHIPPING_INVENTORY_BUFFER=buffer, CJ_STOCK_REFRESH_BATCH_SIZE=batch_size),
        database=database or _Database(),
        provider=provider,
        product_client=SimpleNamespace(list_stock_keys=AsyncMock(return_value=keys)),
        logger=getLogger("test"),
        sleep=sleep,
        clock=lambda: next(clock),
    )
    return service, provider, sleep


def _levels(sent: list[tuple[str, object]]) -> dict[str, dict[str, int]]:
    return {level.supplier_pid: level.variants for _, event in sent for level in event.levels}


# ------------------------------------------------------------ the bug it fixes


async def test_a_product_sold_out_in_the_us_is_sent_as_zero(sent) -> None:
    """The case the catalogue sync can never see: CJ no longer lists it in the US."""
    service, _, _ = _service(
        [SupplierStockKey(supplier_pid="SOLD-OUT", vids=["V-S", "V-M"])],
        {"SOLD-OUT": WarehouseStock(total=0, by_vid={})},
    )

    report = await service.refresh()

    assert _levels(sent) == {"SOLD-OUT": {"V-S": 0, "V-M": 0}}
    assert (report.refreshed, report.sold_out) == (1, 1)
    assert sent[0][0] == SupplierEvents.SUPPLIER_STOCK_UPDATED


async def test_every_product_we_sell_is_asked_about(sent) -> None:
    keys = [SupplierStockKey(supplier_pid=f"P{i}", vids=[f"V{i}"]) for i in range(3)]
    service, provider, _ = _service(keys, {f"P{i}": WarehouseStock(total=i, by_vid={f"V{i}": i}) for i in range(3)})

    await service.refresh()

    assert [c.args[0] for c in provider.get_warehouse_stock.await_args_list] == ["P0", "P1", "P2"]
    assert _levels(sent) == {"P0": {"V0": 0}, "P1": {"V1": 1}, "P2": {"V2": 2}}


# ------------------------------------------------------------------- buffer


async def test_the_buffer_is_held_back_per_variant_and_never_goes_negative(sent) -> None:
    service, _, _ = _service(
        [SupplierStockKey(supplier_pid="P", vids=["V-S", "V-M", "V-L"])],
        {"P": WarehouseStock(total=11, by_vid={"V-S": 10, "V-M": 1})},
        buffer=2,
    )

    await service.refresh()

    assert _levels(sent) == {"P": {"V-S": 8, "V-M": 0, "V-L": 0}}


# ----------------------------------------------------------------- failures


async def test_a_product_cj_could_not_answer_for_keeps_its_stock(sent) -> None:
    """A failed call is not "sold out": zeroing it could hide a product in stock."""
    service, _, _ = _service(
        [SupplierStockKey(supplier_pid="OK", vids=["V1"]), SupplierStockKey(supplier_pid="DOWN", vids=["V2"])],
        {"OK": WarehouseStock(total=4, by_vid={"V1": 4}), "DOWN": CJDropshippingAPIError("503")},
    )

    report = await service.refresh()

    assert _levels(sent) == {"OK": {"V1": 4}}
    assert (report.refreshed, report.failed) == (1, 1)
    assert "DOWN" in report.errors[0]


# -------------------------------------------------------- pacing + batching


async def test_calls_to_cj_are_spaced_to_its_rate_limit(sent) -> None:
    keys = [SupplierStockKey(supplier_pid=f"P{i}", vids=[]) for i in range(3)]
    service, _, sleep = _service(keys, {f"P{i}": WarehouseStock(total=0, by_vid={}) for i in range(3)})

    await service.refresh()

    assert [c.args[0] for c in sleep.await_args_list] == [1.1, 1.1]


async def test_levels_go_out_in_batches_stamped_with_their_earliest_measurement(sent) -> None:
    keys = [SupplierStockKey(supplier_pid=f"P{i}", vids=["V"]) for i in range(5)]
    service, _, _ = _service(keys, {f"P{i}": WarehouseStock(total=1, by_vid={"V": 1}) for i in range(5)}, batch_size=2)

    report = await service.refresh()

    events = [event for _, event in sent]
    assert [len(e.levels) for e in events] == [2, 2, 1]
    assert [e.measured_at for e in events] == [T0, T0 + timedelta(seconds=2), T0 + timedelta(seconds=4)]
    assert report.batches == 3


# -------------------------------------------------------------------- lock


async def test_a_refresh_already_running_is_not_doubled(sent) -> None:
    database = _Database(lock_acquired=False)
    service, provider, _ = _service([SupplierStockKey(supplier_pid="P", vids=[])], {}, database=database)

    report = await service.refresh()

    assert report.skipped_already_running is True
    provider.get_warehouse_stock.assert_not_awaited()
    assert sent == []
    assert not any("unlock" in s for s in database.lock.statements)


async def test_the_lock_is_released_even_when_the_refresh_fails(sent) -> None:
    database = _Database()
    service, _, _ = _service([], {}, database=database)
    service._products.list_stock_keys.side_effect = RuntimeError("product-service down")

    with pytest.raises(RuntimeError):
        await service.refresh()

    assert any("pg_advisory_unlock" in s for s in database.lock.statements)
