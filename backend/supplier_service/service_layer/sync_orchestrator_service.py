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
from exceptions.cj_order_exceptions import ProviderNotFoundError


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
            raise ProviderNotFoundError(
                f"Unsupported provider type '{config.provider_type}'. "
                f"Configured provider: '{self.provider.supplier_id}'."
            )
        return self.provider

    async def run_sync(
        self,
        supplier_id: str,
        filters: CJProductsFilterParams | None = None,
        fetch_details: bool = True,
    ) -> SupplierSyncState:
        """Run a full sync for a supplier and emit a SupplierProductsFetched event.

        The event is written to the outbox table inside the same transaction so
        product_service is guaranteed to receive it even if RabbitMQ is temporarily
        unavailable.
        """
        fetch_id = uuid4()
        now = datetime.now(timezone.utc)
        filters = filters or CJProductsFilterParams()

        config = await self.config_repository.get_by_supplier_id(supplier_id)
        if not config:
            raise CJProductProviderError(f"Supplier config not found: {supplier_id}")
        if not config.is_active:
            raise CJProductProviderError(f"Supplier is not active: {supplier_id}")

        sync_state = SupplierSyncState(
            supplier_id=supplier_id,
            fetch_id=fetch_id,
            status="running",
            products_fetched=0,
            products_emitted=0,
            started_at=now,
        )
        await self.sync_state_repository.create(sync_state)

        try:
            provider = self._get_provider(config)
            page = await provider.search_products(filters)

            products: list[GenericSupplierProduct] = []
            detail_errors: list[str] = []
            if fetch_details:
                products, detail_errors = await self._fetch_product_details(
                    provider=provider,
                    products=page.products,
                    default_category_name=config.default_category_name,
                )
            else:
                products = page.products

            sync_state.products_fetched = len(page.products)
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
            await self.sync_state_repository.update(sync_state)
            raise

    async def _fetch_product_details(
        self,
        provider: SupplierProvider,
        products: list[GenericSupplierProduct],
        default_category_name: str | None,
    ) -> tuple[list[GenericSupplierProduct], list[str]]:
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
