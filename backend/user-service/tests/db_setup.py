from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine

from shared.shared_instances import settings
from shared.models_base_class import Base
from main import app
from dependencies.dependencies import get_db_session


async_engine = create_async_engine(
    url=settings.USER_SERVICE_TEST_DATABASE_URL,
    echo=True)

async_session = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    async with async_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def drop_all_tables():
    async with async_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


def admin_user():
    return {'email': 'a.kostenkouk@gmail.com', 'id': 1, 'user_role': 'admin'}


def normal_user():
    return {'email': 'a.kostenkouk@gmail.com', 'id': 1, 'user_role': 'user'}


# overriding to call our tests db, not production db.....with the db session for tests db with new db url
app.dependency_overrides[get_db_session] = override_get_db_session
