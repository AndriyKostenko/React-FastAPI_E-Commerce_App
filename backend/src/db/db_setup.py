from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from src.config import settings
from sqlalchemy.orm import sessionmaker
from src.models.user_models import Base

async_engine = create_async_engine(
    url=settings.DATABASE_URL,
    echo=True)
async_session = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    async with async_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


# db dependancy
async def get_db_session() -> AsyncSession:
    async with async_session() as session:
        yield session
