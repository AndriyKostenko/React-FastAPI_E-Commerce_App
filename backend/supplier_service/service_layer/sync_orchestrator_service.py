import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from database_layer.supplier_config_repository import SupplierConfigRepository
from database_layer.supplier_sync_state_repository import SupplierSyncStateRepository
from models.supplier_config_models import SupplierConfig
from models.supplier_sync_state_models import SupplierSyncState
from service_layer.outbox_event_service import OutboxEventService
from service_layer.supplier_provider import SupplierProvider
from shared.schemas.dropshipping_schemas import CJProductsFilterParams
from shared.schemas.event_schemas import SupplierProductsFetchedEvent
from shared.schemas.supplier_schemas import GenericSupplierProduct
from shared.settings import Settings
from shared.shared_instances import supplier_service_database_session_manager
from exceptions.cj_order_exceptions import ProviderNotFoundError, SyncAlreadyInProgressError


class SupplierSyncOrchestrator:
    """Orchestrates fetching products from a supplier and emitting import events.

    The provider is injected so the sync workflow stays independent from CJ's
    HTTP and mapping implementation.
    """

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
        """Run a full sync for a supplier and emit a SupplierProductsFetched event."""
        fetch_id = uuid4()
        now = datetime.now(timezone.utc)
        filters = filters or CJProductsFilterParams()

        config = await self.config_repository.get_by_supplier_id(supplier_id)
        if not config:
            raise ProviderNotFoundError(f"Supplier config not found: {supplier_id}")
        if not config.is_active:
            raise ProviderNotFoundError(f"Supplier is not active: {supplier_id}")

        # Check DB-level sync lock for currently running sync
        latest_run = await self.sync_state_repository.get_latest_by_supplier_id(supplier_id)
        if latest_run and latest_run.status == "running":
            raise SyncAlreadyInProgressError(f"Sync already in progress for supplier {supplier_id}")

        # Phase 1: create sync state & commit initial status so concurrent
        # syncs can see the "running" lock in the database.
        sync_state = SupplierSyncState(
            supplier_id=supplier_id,
            fetch_id=fetch_id,
            status="running",
            products_fetched=0,
            products_emitted=0,
            started_at=now,
        )

        await self.sync_state_repository.create(sync_state)
        # Commit early to make the running lock visible outside this transaction.
        await self.sync_state_repository.session.commit()

        # Phase 2: Perform network calls (OUTSIDE DB transaction scope)
        try:
            provider = self._get_provider(config)
            
            all_raw_products: list[GenericSupplierProduct] = []
            current_page = filters.page or 1
            total_pages = 1

            while True:
                page_filters = filters.model_copy(update={"page": current_page})
                page = await provider.search_products(page_filters)
                if not page.products:
                    break
                all_raw_products.extend(page.products)
                if page.total_pages:
                    total_pages = page.total_pages
                if current_page >= total_pages:
                    break
                current_page += 1

            products: list[GenericSupplierProduct] = []
            detail_errors: list[str] = []
            if fetch_details and all_raw_products:
                products, detail_errors = await self._fetch_product_details(
                    provider=provider,
                    products=all_raw_products,
                    default_category_name=config.default_category_name,
                )
            else:
                products = all_raw_products

            # Phase 3: Outbox event & sync state final update in DB
            sync_state.products_fetched = len(all_raw_products)
            sync_state.products_emitted = len(products)

            event = SupplierProductsFetchedEvent(
                supplier_id=supplier_id,
                fetch_id=fetch_id,
                products=products,
            )
            await self.outbox_event_service.add_outbox_event(
                event_type=event.event_type,
                payload=event,
            )

            if detail_errors:
                sync_state.status = "completed_with_errors"
                sync_state.error_message = self._format_detail_errors(detail_errors)
            else:
                sync_state.status = "completed"
            sync_state.finished_at = datetime.now(timezone.utc)

            await self.sync_state_repository.update(sync_state)
            return sync_state

        except Exception as exc:
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

    async def _fetch_product_details(self,
        							provider: SupplierProvider,
               						products: list[GenericSupplierProduct],
                     				default_category_name: str | None) -> tuple[list[GenericSupplierProduct], list[str]]:
        """Fetch details concurrently while protecting the supplier API."""
        semaphore = asyncio.Semaphore(10)

        async def fetch(product: GenericSupplierProduct) -> GenericSupplierProduct | str | None:
            if not product.supplier_pid:
                return "Skipped product without a supplier product id"
            try:
                async with semaphore:
                    detailed = await provider.get_mapped_product_details(product.supplier_pid)
                if default_category_name:
                    detailed.category_name = default_category_name
                return detailed
            except Exception as exc:
                return f"Failed to fetch details for {product.supplier_pid}: {exc}"

        results = await asyncio.gather(*(fetch(product) for product in products))
        detailed_products = [result for result in results if isinstance(result, GenericSupplierProduct)]
        errors = [result for result in results if isinstance(result, str)]
        return detailed_products, errors

    @staticmethod
    def _format_detail_errors(errors: list[str]) -> str:
        """Keep the persisted summary useful without allowing unbounded growth."""
        preview = "; ".join(errors[:10])
        remaining = len(errors) - 10
        return f"{len(errors)} product detail fetches failed. {preview}" + (
            f"; and {remaining} more." if remaining > 0 else ""
        )
