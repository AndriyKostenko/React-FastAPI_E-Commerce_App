from sqlalchemy.ext.asyncio import AsyncSession

from database_layer.supplier_config_repository import SupplierConfigRepository
from models.supplier_config_models import SupplierConfig
from shared.settings import Settings


async def seed_default_supplier_config(session: AsyncSession, settings: Settings) -> None:
    """Ensure a default CJDropshipping supplier config exists.

    This is idempotent: if the config already exists, it is left untouched.
    """
    repository = SupplierConfigRepository(session=session)
    existing = await repository.get_by_supplier_id("cjdropshipping")
    if existing:
        return

    default_config = SupplierConfig(
        supplier_id="cjdropshipping",
        name="CJ Dropshipping",
        provider_type="cjdropshipping",
        is_active=True,
        sync_interval_minutes=60,
        default_category_name=settings.CJ_DROPSHIPPING_DEFAULT_CATEGORY_NAME,
        config={},
    )
    await repository.create(default_config)
