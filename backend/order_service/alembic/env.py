from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
import asyncio

from alembic import context  # type: ignore

from models.base import Base

# Importing every model module is what populates Base.metadata. Autogenerate
# compares against that metadata, so a model left unimported here would look
# like a table the database should drop.
from models.order_address_models import OrderAddress  # noqa: F401
from models.order_models import Order  # noqa: F401
from models.order_item_models import OrderItem  # noqa: F401
from models.order_fulfillment_models import (  # noqa: F401
    CustomProductionJob,
    OrderLineFulfillment,
)
from models.order_saga_models import OrderSagaState  # noqa: F401
from models.outbox_models import OutboxEvent  # noqa: F401
from shared.settings import get_settings


settings = get_settings()

config = context.config

config.set_main_option("sqlalchemy.url", settings.ORDER_SERVICE_DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Helper function to run migrations synchronously within async context."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode with async engine."""
    database_url = config.get_main_option("sqlalchemy.url") or settings.ORDER_SERVICE_DATABASE_URL
    connectable = create_async_engine(
        database_url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
