from fastapi import status
import pytest
from httpx import AsyncClient, ASGITransport

from src import app
from src.tests.db_setup import init_db, drop_all_tables


# using AsyncClient to work with async call to db and async sqlalchemy
@pytest.mark.asyncio
async def test_user_routes():
    async with AsyncClient(transport=ASGITransport(app), base_url="http://127.0.0.1") as client:
        # creating database models in test database
        await init_db()

        response_1 = await client.post('/register', json={'name': 'Andriy Kostenko',
                                                          'email': 'a.kostenkouk@gmail.com',
                                                          'password': '12345678'})
        response_2 = await client.post('/register', json={'name': 'Andriy Kostenko',
                                                          'email': 'a.kostenkouk@gmail.com',
                                                          'password': '12345678'})
        response_3 = await client.post('/register', json={'name': 'Andriy Kostenko',
                                                          'email': 1,
                                                          'password': '12345678'})

        # using 'username' field instead of 'email' field because it takes from OAuth2PasswordRequestForm
        response_4 = await client.post('/login', data={'username': 'a.kostenkouk@gmail.com',
                                                       'password': '12345678'})
        response_5 = await client.post('/login', data={'username': 'a.kostenkouk@gmail.com',
                                                       'password': 'anfjdjfdkdfj111111111111'})

        assert response_1.status_code == status.HTTP_201_CREATED
        assert response_2.status_code == status.HTTP_409_CONFLICT
        assert response_3.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response_4.status_code == status.HTTP_200_OK
        assert response_5.status_code == status.HTTP_401_UNAUTHORIZED

        # cleaning test database
        await drop_all_tables()
