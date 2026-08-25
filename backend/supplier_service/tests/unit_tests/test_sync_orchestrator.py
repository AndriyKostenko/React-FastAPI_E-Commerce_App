from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from exceptions.cj_order_exceptions import (
    ProviderNotFoundError,
    SupplierSyncConfigurationError,
    SyncAlreadyInProgressError,
)
from service_layer.sync_orchestrator_service import SupplierSyncOrchestrator
from schemas.dropshipping_schemas import CJProductsFilterParams
from shared.contracts.supplier import GenericSupplierProduct
from schemas.supplier_schemas import SupplierProductsPage


def _product(pid: str | None) -> GenericSupplierProduct:
    return GenericSupplierProduct(
        supplier_id="cjdropshipping",
        supplier_pid=pid,
        name="Test product",
        price="10.00",
        supplier_category_id="tshirt-cat",
    )


class FakeCJProvider:
    supplier_id = "cjdropshipping"

    def __init__(
        self,
        details: dict[str, GenericSupplierProduct | Exception],
        list_products: list[GenericSupplierProduct] | None = None,
    ) -> None:
        self.details = details
        self.list_products = list_products or [_product(pid) for pid in details]
        self.search_filters: list[CJProductsFilterParams] = []

    async def search_products(self, filters_query: CJProductsFilterParams) -> SupplierProductsPage:
        self.search_filters.append(filters_query)
        return SupplierProductsPage(
            page=filters_query.page,
            page_size=filters_query.size,
            products=self.list_products,
        )

    async def get_mapped_product_details(self, supplier_pid: str) -> GenericSupplierProduct:
        result = self.details[supplier_pid]
        if isinstance(result, Exception):
            raise result
        return result


def _orchestrator(provider: FakeCJProvider):
    config_repository = SimpleNamespace(
        get_by_supplier_id=AsyncMock(
            return_value=SimpleNamespace(
                supplier_id="cjdropshipping",
                provider_type="cjdropshipping",
                is_active=True,
                default_category_name="Imported",
                config={"allowed_category_ids": ["tshirt-cat"]},
            )
        )
    )
    sync_state_repository = SimpleNamespace(
        create=AsyncMock(),
        update=AsyncMock(),
        get_latest_by_supplier_id=AsyncMock(return_value=None),
        session=SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock()),
    )
    outbox_event_service = SimpleNamespace(add_outbox_event=AsyncMock())
    return (
        SupplierSyncOrchestrator(
            settings=SimpleNamespace(),
            config_repository=config_repository,
            sync_state_repository=sync_state_repository,
            outbox_event_service=outbox_event_service,
            provider=provider,
        ),
        config_repository,
        sync_state_repository,
        outbox_event_service,
    )


@pytest.mark.asyncio
async def test_sync_persists_event_and_marks_complete() -> None:
    provider = FakeCJProvider({"one": _product("one")})
    orchestrator, _, _, outbox = _orchestrator(provider)

    state = await orchestrator.run_sync("cjdropshipping")

    assert state.status == "awaiting_import"
    assert state.products_fetched == 1
    assert state.products_emitted == 1
    assert state.error_message is None
    emitted_event = outbox.add_outbox_event.await_args.kwargs["payload"]
    assert emitted_event.products[0].category_name == "Imported"
    assert emitted_event.batch_number == 1
    assert emitted_event.total_batches == 1
    assert provider.search_filters[0].keyWord == "t-shirt"
    assert provider.search_filters[0].lv3categoryList == ["tshirt-cat"]


@pytest.mark.asyncio
async def test_sync_preserves_inventory_from_product_list_when_details_omit_it() -> None:
    preview = _product("one")
    preview.quantity = 160000
    preview.in_stock = True

    details = _product("one")
    details.quantity = 0
    details.in_stock = False
    provider = FakeCJProvider({"one": details}, list_products=[preview])
    orchestrator, _, _, outbox = _orchestrator(provider)

    await orchestrator.run_sync("cjdropshipping")

    emitted_product = outbox.add_outbox_event.await_args.kwargs["payload"].products[0]
    assert emitted_product.quantity == 160000
    assert emitted_product.in_stock is True


@pytest.mark.asyncio
async def test_single_product_sync_emits_only_requested_product() -> None:
    provider = FakeCJProvider(
        {
            "requested": _product("requested"),
            "unrelated": _product("unrelated"),
        }
    )
    orchestrator, _, _, outbox = _orchestrator(provider)

    state = await orchestrator.run_product_sync("cjdropshipping", "requested")

    assert state.status == "awaiting_import"
    assert state.products_fetched == 1
    assert state.products_emitted == 1
    assert state.total_batches == 1
    emitted_event = outbox.add_outbox_event.await_args.kwargs["payload"]
    assert [product.supplier_pid for product in emitted_event.products] == ["requested"]
    assert emitted_event.products[0].category_name == "Imported"
    assert provider.search_filters == []


@pytest.mark.asyncio
async def test_single_product_sync_rolls_back_and_marks_failure() -> None:
    provider = FakeCJProvider({"requested": _product("requested")})
    orchestrator, _, sync_state_repository, outbox = _orchestrator(provider)
    outbox.add_outbox_event.side_effect = RuntimeError("outbox unavailable")

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        await orchestrator.run_product_sync("cjdropshipping", "requested")

    sync_state_repository.session.rollback.assert_awaited_once()
    failed_state = sync_state_repository.update.await_args.args[0]
    assert failed_state.status == "failed"
    assert failed_state.error_message == "outbox unavailable"


@pytest.mark.asyncio
async def test_sync_records_partial_detail_failures() -> None:
    provider = FakeCJProvider({"good": _product("good"), "bad": RuntimeError("CJ unavailable")})
    orchestrator, _, _, outbox = _orchestrator(provider)

    state = await orchestrator.run_sync("cjdropshipping")

    assert state.status == "awaiting_import_with_errors"
    assert state.products_fetched == 2
    assert state.products_emitted == 1
    assert "1 product detail fetches failed" in state.error_message
    emitted_event = outbox.add_outbox_event.await_args.kwargs["payload"]
    assert [product.supplier_pid for product in emitted_event.products] == ["good"]


@pytest.mark.asyncio
async def test_unknown_supplier_config_fails_before_creating_sync_state() -> None:
    provider = FakeCJProvider({"one": _product("one")})
    orchestrator, config_repository, _, _ = _orchestrator(provider)
    config_repository.get_by_supplier_id.return_value = None

    with pytest.raises(ProviderNotFoundError, match="Supplier config not found"):
        await orchestrator.run_sync("missing")


@pytest.mark.asyncio
async def test_sync_raises_when_already_in_progress() -> None:
    provider = FakeCJProvider({"one": _product("one")})
    orchestrator, _, sync_state_repository, _ = _orchestrator(provider)
    sync_state_repository.get_latest_by_supplier_id.return_value = SimpleNamespace(status="running")

    with pytest.raises(SyncAlreadyInProgressError, match="Sync already in progress"):
        await orchestrator.run_sync("cjdropshipping")


@pytest.mark.asyncio
async def test_sync_rejects_detail_outside_tshirt_allowlist() -> None:
    other = _product("other")
    other.supplier_category_id = "hoodie-cat"
    provider = FakeCJProvider({"other": other})
    orchestrator, _, _, outbox = _orchestrator(provider)

    state = await orchestrator.run_sync("cjdropshipping")

    assert state.status == "awaiting_import_with_errors"
    assert state.products_emitted == 0
    event = outbox.add_outbox_event.await_args.kwargs["payload"]
    assert event.products == []
    assert "not an allowed T-shirt category" in state.error_message


@pytest.mark.asyncio
async def test_sync_requires_explicit_tshirt_category_policy() -> None:
    provider = FakeCJProvider({"one": _product("one")})
    orchestrator, config_repository, _, _ = _orchestrator(provider)
    config_repository.get_by_supplier_id.return_value.config = {}

    with pytest.raises(SupplierSyncConfigurationError, match="allowed_category_ids"):
        await orchestrator.run_sync("cjdropshipping")


@pytest.mark.asyncio
async def test_sync_commits_each_batch_before_fetching_next_supplier_page() -> None:
    provider = FakeCJProvider({}, list_products=[])
    orchestrator, _, sync_state_repository, _ = _orchestrator(provider)
    requested_pages: list[int] = []

    async def search_products(filters: CJProductsFilterParams) -> SupplierProductsPage:
        requested_pages.append(filters.page)
        # One commit records the running state; every later supplier request
        # must see the previous outbox batch committed as well.
        assert sync_state_repository.session.commit.await_count == len(requested_pages)
        return SupplierProductsPage(
            page=filters.page,
            page_size=filters.size,
            total_pages=2,
            products=[],
        )

    provider.search_products = AsyncMock(side_effect=search_products)

    await orchestrator.run_sync("cjdropshipping")

    assert requested_pages == [1, 2]
