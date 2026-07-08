from datetime import datetime, timezone
from uuid import uuid4

from database_layer.supplier_config_repository import SupplierConfigRepository
from database_layer.supplier_sync_state_repository import SupplierSyncStateRepository
from models.supplier_config_models import SupplierConfig
from models.supplier_sync_state_models import SupplierSyncState
from service_layer.cj_product_provider import CJDropshippingProductProvider
from service_layer.outbox_event_service import OutboxEventService
from service_layer.supplier_provider import SupplierProvider
from shared.schemas.dropshipping_schemas import CJProductsFilterParams
from shared.schemas.event_schemas import SupplierProductsFetchedEvent
from shared.schemas.supplier_schemas import GenericSupplierProduct
from shared.settings import Settings


class SupplierSyncOrchestrator:
    """Orchestrates fetching products from a supplier and emitting import events."""

    def __init__(
        self,
        settings: Settings,
        config_repository: SupplierConfigRepository,
        sync_state_repository: SupplierSyncStateRepository,
        outbox_event_service: OutboxEventService,
    ) -> None:
        self.settings: Settings = settings
        self.config_repository: SupplierConfigRepository = config_repository
        self.sync_state_repository: SupplierSyncStateRepository = sync_state_repository
        self.outbox_event_service: OutboxEventService = outbox_event_service

    def _get_provider(self, config: SupplierConfig) -> SupplierProvider:
        """Resolve the correct provider implementation for a supplier config."""
        if config.provider_type == "cjdropshipping":
            return CJDropshippingProductProvider(self.settings)
        raise ValueError(f"Unknown provider type: {config.provider_type}")

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
            raise ValueError(f"Supplier config not found: {supplier_id}")
        if not config.is_active:
            raise ValueError(f"Supplier is not active: {supplier_id}")

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
            if fetch_details:
                for product in page.products:
                    if not product.supplier_pid:
                        continue
                    try:
                        detailed = await provider.get_mapped_product_details(product.supplier_pid)
                        if config.default_category_name:
                            detailed.category_name = config.default_category_name
                        products.append(detailed)
                    except Exception as exc:
                        sync_state.error_message = f"Failed to fetch details for {product.supplier_pid}: {exc}"
            else:
                products = page.products

            sync_state.products_fetched = len(page.products)
            sync_state.products_emitted = len(products)

            # Build and persist the outbox event in the same session/transaction.
            event = SupplierProductsFetchedEvent(
                supplier_id=supplier_id,
                fetch_id=fetch_id,
                products=products,
            )
            await self.outbox_event_service.add_outbox_event(
                event_type=event.event_type,
                payload=event,
            )

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
