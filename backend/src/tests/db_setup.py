from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.db.db_setup import get_db_session
from src.models.user_model import Base
from src import app
from src.config import settings


async_engine = create_async_engine(
    url=settings.TEST_DATABASE_URL,
    echo=True)

async_session = sessionmaker(
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


async def override_get_db_session() -> AsyncSession:
    async with async_session() as session:
        yield session


def admin_user():
    return {'email': 'a.kostenkouk@gmail.com', 'id': 1, 'user_role': 'admin'}


def normal_user():
    return {'email': 'a.kostenkouk@gmail.com', 'id': 1, 'user_role': 'user'}


# overriding to call our tests db, not production db.....with the db session for tests db with new db url
app.dependency_overrides[get_db_session] = override_get_db_session
