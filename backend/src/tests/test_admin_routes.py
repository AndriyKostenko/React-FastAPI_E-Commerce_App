from fastapi import status
import pytest
from httpx import AsyncClient, ASGITransport

from src import app
from src.security.authentication import get_current_user
from src.tests.db_setup import init_db, drop_all_tables, admin_user, normal_user

# marking with package to use same event_loop() for all tests in package
pytestmark = pytest.mark.asyncio(scope="package")


# using AsyncClient to work with async calls to db and async sqlalchemy
async def test_admin_routes():
    async with AsyncClient(transport=ASGITransport(app), base_url="http://127.0.0.1") as client:
        # creating database models in tests database
        await init_db()

        # overriding the current_user() as ADMIN for our tests only
        app.dependency_overrides[get_current_user] = admin_user
        response_1 = await client.get('/admin/users')
        assert response_1.status_code == status.HTTP_200_OK

        # overriding the current_user() as NORMAL user for our tests only
        app.dependency_overrides[get_current_user] = normal_user
        response_2 = await client.get('/admin/users')
        assert response_2.status_code == status.HTTP_401_UNAUTHORIZED

        # cleaning tests database
        await drop_all_tables()
