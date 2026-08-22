import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.exc import IntegrityError

from database_layer.supplier_config_repository import SupplierConfigRepository
from database_layer.supplier_sync_state_repository import SupplierSyncStateRepository
from models.supplier_config_models import SupplierConfig
from models.supplier_sync_state_models import SupplierSyncState
from service_layer.outbox_event_service import OutboxEventService
from service_layer.supplier_provider import SupplierProvider
from schemas.dropshipping_schemas import CJProductsFilterParams
from shared.contracts.events import SupplierProductsFetchedEvent
from shared.contracts.supplier import GenericSupplierProduct
from shared.settings import Settings
from exceptions.cj_order_exceptions import (
    ProviderNotFoundError,
    SupplierSyncConfigurationError,
    SyncAlreadyInProgressError,
)


class SupplierSyncOrchestrator:
    """Orchestrates fetching products from a supplier and emitting import events.

    The provider is injected so the sync workflow stays independent from CJ's
    HTTP and mapping implementation.
    """

    ACTIVE_STATUSES = {
        "running",
        "awaiting_import",
        "awaiting_import_with_errors",
        "importing",
    }

    def __init__(
        self,
        settings: Settings,
        config_repository: SupplierConfigRepository,
        sync_state_repository: SupplierSyncStateRepository,
        outbox_event_service: OutboxEventService,
        provider: SupplierProvider,
    ) -> None:
        self.settings: Settings = settings
        self.config_repository: SupplierConfigRepository = config_repository
        self.sync_state_repository: SupplierSyncStateRepository = sync_state_repository
        self.outbox_event_service: OutboxEventService = outbox_event_service
        self.provider: SupplierProvider = provider

    def _get_provider(self, config: SupplierConfig) -> SupplierProvider:
        """Look up the provider for a given supplier config."""
        if config.provider_type != self.provider.supplier_id:
            raise ProviderNotFoundError(f"Unsupported provider type '{config.provider_type}'.Configured provider: '{self.provider.supplier_id}'.")
        return self.provider

    async def run_sync(
        self,
        supplier_id: str,
        filters: CJProductsFilterParams | None = None,
        fetch_details: bool = True,
    ) -> SupplierSyncState:
        """Fetch and emit bounded, category-safe supplier product batches."""
        fetch_id = uuid4()
        now = datetime.now(timezone.utc)
        filters = filters or CJProductsFilterParams()

        if not fetch_details:
            raise SupplierSyncConfigurationError(
                "Persistent supplier sync requires full product details and variants. "
                "Use the preview endpoint for list-only searches."
            )

        config = await self.config_repository.get_by_supplier_id(supplier_id)
        if not config:
            raise ProviderNotFoundError(f"Supplier config not found: {supplier_id}")
        if not config.is_active:
            raise ProviderNotFoundError(f"Supplier is not active: {supplier_id}")

        # Check DB-level sync lock for currently running sync
        latest_run = await self.sync_state_repository.get_latest_by_supplier_id(supplier_id)
        if latest_run and latest_run.status in self.ACTIVE_STATUSES:
            raise SyncAlreadyInProgressError(f"Sync already in progress for supplier {supplier_id}")

        # Phase 1: create sync state & commit initial status so concurrent
        # syncs can see the "running" lock in the database.
        sync_state = SupplierSyncState(
            supplier_id=supplier_id,
            fetch_id=fetch_id,
            status="running",
            products_fetched=0,
            products_emitted=0,
            total_batches=0,
            processed_batches=0,
            products_imported=0,
            products_updated=0,
            products_failed=0,
            acknowledged_batch_ids=[],
            started_at=now,
        )

        try:
            await self.sync_state_repository.create(sync_state)
            # Commit early to make the running lock visible outside this transaction.
            await self.sync_state_repository.session.commit()
        except IntegrityError as exc:
            await self.sync_state_repository.session.rollback()
            raise SyncAlreadyInProgressError(
                f"Sync already in progress for supplier {supplier_id}"
            ) from exc

        # Phase 2: Perform network calls (OUTSIDE DB transaction scope)
        try:
            provider = self._get_provider(config)
            
            allowed_category_ids = self._get_allowed_category_ids(config)
            filters = filters.model_copy(
                update={
                    "keyWord": "t-shirt",
                    "categoryId": None,
                    "lv2categoryList": None,
                    "lv3categoryList": sorted(allowed_category_ids),
                }
            )

            current_page = filters.page or 1
            first_page = current_page
            total_pages: int | None = None
            detail_errors: list[str] = []

            while True:
                page_filters = filters.model_copy(update={"page": current_page})
                page = await provider.search_products(page_filters)
                if total_pages is None:
                    total_pages = max(int(page.total_pages or current_page), current_page)
                    sync_state.total_batches = max(total_pages - first_page + 1, 1)

                sync_state.products_fetched += len(page.products)
                page_errors: list[str] = []
                if fetch_details and page.products:
                    products, page_errors = await self._fetch_product_details(
                        provider=provider,
                        products=page.products,
                        default_category_name=config.default_category_name,
                        allowed_category_ids=allowed_category_ids,
                    )
                else:
                    products = [
                        product
                        for product in page.products
                        if product.supplier_category_id in allowed_category_ids
                    ]

                detail_errors.extend(page_errors)
                sync_state.products_emitted += len(products)
                batch_number = current_page - first_page + 1
                event = SupplierProductsFetchedEvent(
                    supplier_id=supplier_id,
                    fetch_id=fetch_id,
                    batch_number=batch_number,
                    total_batches=sync_state.total_batches,
                    products=products,
                )
                await self.outbox_event_service.add_outbox_event(
                    event_type=event.event_type,
                    payload=event,
                )

                if current_page >= total_pages:
                    break
                current_page += 1

            if detail_errors:
                sync_state.status = "awaiting_import_with_errors"
                sync_state.error_message = self._format_detail_errors(detail_errors)
            else:
                sync_state.status = "awaiting_import"

            await self.sync_state_repository.update(sync_state)
            return sync_state

        except Exception as exc:
            await self.sync_state_repository.session.rollback()
            sync_state.status = "failed"
            sync_state.finished_at = datetime.now(timezone.utc)
            sync_state.error_message = str(exc)
            try:
                await self.sync_state_repository.update(sync_state)
                # Commit before re-raising so the failed state is persisted;
                # the surrounding transaction manager will roll back the new
                # transaction that starts after this commit.
                await self.sync_state_repository.session.commit()
            except Exception:
                pass
            raise

    async def run_product_sync(
        self,
        supplier_id: str,
        supplier_pid: str,
    ) -> SupplierSyncState:
        """Fetch and emit exactly one supplier product by its stable ID."""
        fetch_id = uuid4()
        now = datetime.now(timezone.utc)

        config = await self.config_repository.get_by_supplier_id(supplier_id)
        if not config:
            raise ProviderNotFoundError(f"Supplier config not found: {supplier_id}")
        if not config.is_active:
            raise ProviderNotFoundError(f"Supplier is not active: {supplier_id}")

        latest_run = await self.sync_state_repository.get_latest_by_supplier_id(supplier_id)
        if latest_run and latest_run.status in self.ACTIVE_STATUSES:
            raise SyncAlreadyInProgressError(f"Sync already in progress for supplier {supplier_id}")

        sync_state = SupplierSyncState(
            supplier_id=supplier_id,
            fetch_id=fetch_id,
            status="running",
            products_fetched=0,
            products_emitted=0,
            total_batches=1,
            processed_batches=0,
            products_imported=0,
            products_updated=0,
            products_failed=0,
            acknowledged_batch_ids=[],
            started_at=now,
        )

        try:
            await self.sync_state_repository.create(sync_state)
            await self.sync_state_repository.session.commit()
        except IntegrityError as exc:
            await self.sync_state_repository.session.rollback()
            raise SyncAlreadyInProgressError(
                f"Sync already in progress for supplier {supplier_id}"
            ) from exc

        try:
            provider = self._get_provider(config)
            allowed_category_ids = self._get_allowed_category_ids(config)
            product = await provider.get_mapped_product_details(supplier_pid)
            sync_state.products_fetched = 1

            if product.supplier_category_id not in allowed_category_ids:
                raise SupplierSyncConfigurationError(
                    f"Product {supplier_pid} category '{product.supplier_category_id}' "
                    "is not an allowed T-shirt category"
                )

            if config.default_category_name:
                product.category_name = config.default_category_name

            event = SupplierProductsFetchedEvent(
                supplier_id=supplier_id,
                fetch_id=fetch_id,
                batch_number=1,
                total_batches=1,
                products=[product],
            )
            await self.outbox_event_service.add_outbox_event(
                event_type=event.event_type,
                payload=event,
            )

            sync_state.products_emitted = 1
            sync_state.status = "awaiting_import"
            await self.sync_state_repository.update(sync_state)
            return sync_state
        except Exception as exc:
            await self.sync_state_repository.session.rollback()
            sync_state.status = "failed"
            sync_state.finished_at = datetime.now(timezone.utc)
            sync_state.error_message = str(exc)
            try:
                await self.sync_state_repository.update(sync_state)
                await self.sync_state_repository.session.commit()
            except Exception:
                pass
            raise

    async def _fetch_product_details(self,
        							provider: SupplierProvider,
               						products: list[GenericSupplierProduct],
                                 default_category_name: str | None,
                                 allowed_category_ids: set[str]) -> tuple[list[GenericSupplierProduct], list[str]]:
        """Fetch details concurrently while protecting the supplier API."""
        semaphore = asyncio.Semaphore(10)

        async def fetch(product: GenericSupplierProduct) -> GenericSupplierProduct | str | None:
            if not product.supplier_pid:
                return "Skipped product without a supplier product id"
            try:
                async with semaphore:
                    detailed = await provider.get_mapped_product_details(product.supplier_pid)
                if detailed.supplier_category_id not in allowed_category_ids:
                    return (
                        f"Skipped {product.supplier_pid}: category "
                        f"'{detailed.supplier_category_id}' is not an allowed T-shirt category"
                    )
                if default_category_name:
                    detailed.category_name = default_category_name
                return detailed
            except Exception as exc:
                return f"Failed to fetch details for {product.supplier_pid}: {exc}"

        results = await asyncio.gather(*(fetch(product) for product in products))
        detailed_products = [result for result in results if isinstance(result, GenericSupplierProduct)]
        errors = [result for result in results if isinstance(result, str)]
        return detailed_products, errors

    def _get_allowed_category_ids(self, config: SupplierConfig) -> set[str]:
        configured = (config.config or {}).get("allowed_category_ids") or []
        setting_values = getattr(self.settings, "CJ_DROPSHIPPING_TSHIRT_CATEGORY_IDS", [])
        allowed = {str(value).strip() for value in [*configured, *setting_values] if str(value).strip()}
        if not allowed:
            raise SupplierSyncConfigurationError(
                "Configure at least one CJ T-shirt category ID in supplier config "
                "'allowed_category_ids' or CJ_DROPSHIPPING_TSHIRT_CATEGORY_IDS."
            )
        return allowed

    @staticmethod
    def _format_detail_errors(errors: list[str]) -> str:
        """Keep the persisted summary useful without allowing unbounded growth."""
        preview = "; ".join(errors[:10])
        remaining = len(errors) - 10
        return f"{len(errors)} product detail fetches failed. {preview}" + (
            f"; and {remaining} more." if remaining > 0 else ""
        )
