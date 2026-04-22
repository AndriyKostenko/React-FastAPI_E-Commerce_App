import asyncio
import sys
import os
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context  # type: ignore

# Make sure the backend root is on sys.path so `shared` and local `models` are importable.
_HERE = Path(__file__).resolve().parent          # alembic/
_SERVICE_ROOT = _HERE.parent                      # payment_service/
_BACKEND_ROOT = _SERVICE_ROOT.parent              # backend/

for p in (_SERVICE_ROOT, _BACKEND_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from shared.models.models_base_class import Base  # noqa: E402
from shared.models.outbox_events import OutboxEvent  # noqa: E402, F401  — registers table with Base
from models.payment_models import Payment  # noqa: E402, F401  — registers table with Base
from shared.settings import Settings  # noqa: E402

_settings = Settings()

config = context.config
config.set_main_option("sqlalchemy.url", _settings.PAYMENT_SERVICE_DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
