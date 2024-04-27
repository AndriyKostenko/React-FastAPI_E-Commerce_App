import asyncio

import pytest
from src.service.user_service import UserCRUDService
from src.models.user_model import User
from src.schemas.user_schemas import UserSignUp
from sqlalchemy.ext.asyncio import AsyncSession

from src.tests.db_setup import async_session, init_db, drop_all_tables

# marking with package to use same event_loop() for all tests in package
pytestmark = pytest.mark.asyncio(scope="package")


# creating custom context manager for async session
class AsyncSessionContextManager:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.session = None

    async def __aenter__(self):
        if asyncio.iscoroutinefunction(self.session_factory):
            self.session = await self.session_factory()
        else:
            self.session = self.session_factory
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()


async def override_get_db_session() -> AsyncSessionContextManager:
    return AsyncSessionContextManager(async_session())


async def test_CRUD_user():
    #initialising db
    await init_db()

    async with await override_get_db_session() as session:
        user_service = UserCRUDService(session=session)

        created_user = await user_service.create_user(user=UserSignUp(name="test",
                                                                      email="test@gmail.com",
                                                                      password="testpassword"))

        authenticated_user = await user_service.authenticate_user(email="test@example.com",
                                                                  entered_password="testpassword")

        assert created_user.email == "test@gmail.com"
        assert authenticated_user == False

    # clearing db
    await drop_all_tables()
