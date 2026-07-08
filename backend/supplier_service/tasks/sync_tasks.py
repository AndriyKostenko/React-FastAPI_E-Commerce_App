from datetime import datetime, timezone
from typing import Any

from tasks.broker import taskiq_broker
from database_layer.supplier_config_repository import SupplierConfigRepository
from database_layer.supplier_sync_state_repository import SupplierSyncStateRepository
from models.supplier_config_models import SupplierConfig
from service_layer.outbox_event_service import OutboxEventService
from service_layer.sync_orchestrator_service import SupplierSyncOrchestrator
from shared.database_layer.outbox_repository import OutboxRepository
from shared.schemas.dropshipping_schemas import CJProductsFilterParams
from shared.settings import Settings
from shared.shared_instances import logger, settings, supplier_service_database_session_manager


@taskiq_broker.task(schedule=[{"cron": "*/10 * * * *"}])
async def scheduled_supplier_sync() -> dict[str, Any]:
    """Periodic task that syncs all active suppliers every 10 minutes.

    The cron schedule is a sensible default; it can be adjusted via the TaskIQ
    scheduler configuration or by calling the manual sync endpoint.
    """
    from uuid import uuid4

    results: list[dict[str, Any]] = []
    async with supplier_service_database_session_manager.transaction() as session:
        config_repository = SupplierConfigRepository(session=session)
        sync_state_repository = SupplierSyncStateRepository(session=session)
        outbox_event_service = OutboxEventService(repository=OutboxRepository(session=session))
        orchestrator = SupplierSyncOrchestrator(
            settings=settings,
            config_repository=config_repository,
            sync_state_repository=sync_state_repository,
            outbox_event_service=outbox_event_service,
        )

        active_configs: list[SupplierConfig] = await config_repository.get_active()
        if not active_configs:
            logger.info("No active supplier configs found; skipping scheduled sync.")
            return {"synced_at": datetime.now(timezone.utc).isoformat(), "results": results}

        for config in active_configs:
            try:
                sync_state = await orchestrator.run_sync(
                    supplier_id=config.supplier_id,
                    filters=CJProductsFilterParams(),
                    fetch_details=True,
                )
                results.append({
                    "supplier_id": config.supplier_id,
                    "status": sync_state.status,
                    "products_fetched": sync_state.products_fetched,
                    "products_emitted": sync_state.products_emitted,
                })
            except Exception as exc:
                logger.error(f"Scheduled sync failed for supplier {config.supplier_id}: {exc}")
                results.append({
                    "supplier_id": config.supplier_id,
                    "status": "failed",
                    "error": str(exc),
                })

    return {"synced_at": datetime.now(timezone.utc).isoformat(), "results": results}
