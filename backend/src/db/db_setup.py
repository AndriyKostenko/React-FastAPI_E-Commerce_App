from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from src.config import settings
from sqlalchemy.orm import sessionmaker
from src.models.user_models import Base



# create async engine
async_engine = create_async_engine(
    url=settings.DATABASE_URL,
    echo=True
) # # Set to False in production to avoid logging SQL queries

# create async session
async_session = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# create tables
async def init_db():
    async with async_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


# db dependency for async session
async def get_db_session():
    async with async_session() as session:
        yield session
