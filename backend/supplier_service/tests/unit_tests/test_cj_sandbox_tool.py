"""The dev.sh cj-sandbox helper: what it refuses, and what it asks CJ's sandbox to do."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import tools.cj_sandbox as tool
from service_layer.cj_api_client import CJDropshippingAPIError
from tools.cj_sandbox import CJSandboxDriver, SandboxOrder, SandboxOrderError

ORDER_ID = uuid4()


def _driver(monkeypatch, attempt: SimpleNamespace | None) -> tuple[CJSandboxDriver, MagicMock]:
    class _Repo:
        def __init__(self, _session) -> None: ...

        async def get_by_field(self, _field, _value):
            return attempt

    @asynccontextmanager
    async def transaction():
        yield MagicMock()

    monkeypatch.setattr(tool, "CJOrderAttemptRepository", _Repo)
    cj = MagicMock()
    cj.sandbox_update_status = AsyncMock(return_value={"result": True})
    cj.sandbox_update_track_number = AsyncMock(return_value={"result": True})
    return CJSandboxDriver(SimpleNamespace(transaction=transaction), cj), cj


def _attempt(**overrides) -> SimpleNamespace:
    values = dict(order_id=ORDER_ID, cj_order_number="SD-1", status="paid", is_sandbox=True)
    return SimpleNamespace(**{**values, **overrides})


def _order() -> SandboxOrder:
    return SandboxOrder(ORDER_ID, "SD-1", "paid")


# ------------------------------------------------------------------ refusals


async def test_a_real_cj_order_is_never_touched(monkeypatch) -> None:
    driver, cj = _driver(monkeypatch, _attempt(is_sandbox=False))

    with pytest.raises(SandboxOrderError, match="real CJ order"):
        await driver.load(ORDER_ID)

    cj.sandbox_update_status.assert_not_called()


@pytest.mark.parametrize(
    ("attempt", "message"),
    [(None, "No CJ order"), (_attempt(cj_order_number=None, status="creating"), "no CJ order number")],
)
async def test_an_order_without_a_cj_order_is_refused(monkeypatch, attempt, message: str) -> None:
    driver, _ = _driver(monkeypatch, attempt)

    with pytest.raises(SandboxOrderError, match=message):
        await driver.load(ORDER_ID)


async def test_a_sandbox_order_loads(monkeypatch) -> None:
    driver, _ = _driver(monkeypatch, _attempt())

    assert await driver.load(ORDER_ID) == _order()


# ------------------------------------------------------------------- driving


async def test_shipping_sets_the_tracking_number_before_the_shipped_status(monkeypatch) -> None:
    driver, cj = _driver(monkeypatch, _attempt())
    calls: list[tuple] = []
    cj.sandbox_update_track_number.side_effect = lambda *args: calls.append(("track", *args))
    cj.sandbox_update_status.side_effect = lambda *args: calls.append(("status", *args))

    await driver.ship(_order(), "SBX1")

    # The poller announces "shipped" only with a tracking number to give.
    assert calls == [("track", "SD-1", "SBX1"), ("status", "SD-1", 400), ("status", "SD-1", 500)]


async def test_delivering_walks_every_step_cj_requires(monkeypatch) -> None:
    driver, cj = _driver(monkeypatch, _attempt())

    await driver.deliver(_order())

    assert [c.args[1] for c in cj.sandbox_update_status.await_args_list] == [400, 500, 600]


async def test_a_step_already_passed_is_skipped(monkeypatch) -> None:
    """After `ship`, `deliver` finds 400 and 500 done; CJ refuses those, 600 still goes."""
    driver, cj = _driver(monkeypatch, _attempt())

    async def update(_order_id: str, status: int):
        if status < 600:
            raise CJDropshippingAPIError("status cannot be reverted")
        return {"result": True}

    cj.sandbox_update_status.side_effect = update

    await driver.deliver(_order())

    assert cj.sandbox_update_status.await_count == 3


async def test_a_refused_final_step_is_an_error(monkeypatch) -> None:
    driver, cj = _driver(monkeypatch, _attempt())
    cj.sandbox_update_status.side_effect = CJDropshippingAPIError("not a sandbox order")

    with pytest.raises(CJDropshippingAPIError):
        await driver.deliver(_order())
