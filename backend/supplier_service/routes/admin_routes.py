from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.dependencies import get_db_session
from models.cj_order_attempt_models import CJOrderAttempt
from models.supplier_config_models import SupplierConfig
from models.supplier_sync_state_models import SupplierSyncState
from schemas.admin_schemas import (
    CJOrderAdminSchema,
    SupplierConfigAdminSchema,
    SupplierConfigAdminUpdate,
    SupplierSyncAdminSchema,
)
from shared.admin.admin_tables import AdminTable, AdminTableRouter
from shared.auth.route_guards import AdminDep

# CJ orders are read-only here: they move through the confirm/pay/track
# workflow; a stuck one is handled with the cj-sandbox / reconciliation tools.
admin_routes = AdminTableRouter(get_db_session).build([
    AdminTable("cj-orders", CJOrderAttempt, CJOrderAdminSchema, filterable=("status", "order_id", "is_sandbox")),
    AdminTable("supplier-syncs", SupplierSyncState, SupplierSyncAdminSchema, filterable=("status", "supplier_id"),
               order_by="started_at"),
    AdminTable("supplier-configs", SupplierConfig, SupplierConfigAdminSchema, filterable=("is_active",)),
])

supplier_config_admin_routes = APIRouter(tags=["admin"])


@supplier_config_admin_routes.patch(
    "/admin/supplier-configs/{config_id}",
    response_model=SupplierConfigAdminSchema,
    summary="Pause or resume a supplier's catalogue sync, or change its interval (admin)",
)
async def update_supplier_config(
    config_id: UUID,
    changes: SupplierConfigAdminUpdate,
    admin: AdminDep,
    session: AsyncSession = Depends(get_db_session, scope="function"),
) -> SupplierConfigAdminSchema:
    config = await session.get(SupplierConfig, config_id, with_for_update=True)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such supplier config")
    for field, value in changes.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(config, field, value)
    await session.flush()
    await session.refresh(config)
    return SupplierConfigAdminSchema.model_validate(config, from_attributes=True)
