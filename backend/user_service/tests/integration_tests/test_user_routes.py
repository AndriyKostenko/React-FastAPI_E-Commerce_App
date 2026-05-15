from httpx import AsyncClient
import pytest
from fastapi import status


pytestmark = pytest.mark.asyncio(scope="package")


async def test_user_routes(integration_client: AsyncClient, mock_user_events_publisher):
        # ── Register new user ────────────────────────────────────────────────
        response_1 = await integration_client.post('/api/v1/register', json={'name': 'Andriy Kostenko',
                                                          'email': 'a.kostenkouk@gmail.com',
                                                          'password': '12345678'})
        # ── Duplicate email → 409 ────────────────────────────────────────────
        response_2 = await integration_client.post('/api/v1/register', json={'name': 'Andriy Kostenko',
                                                          'email': 'a.kostenkouk@gmail.com',
                                                          'password': '12345678'})
        # ── Invalid email type → 422 ─────────────────────────────────────────
        response_3 = await integration_client.post('/api/v1/register', json={'name': 'Andriy Kostenko',
                                                          'email': 1,
                                                          'password': '12345678'})

        # ── Activate email using the token captured from the mock publisher ──
        # publish_user_registered(email, verification_token, user_id=...)
        verification_token = mock_user_events_publisher.publish_user_registered.call_args.args[1]
        await integration_client.post(f'/api/v1/activate/{verification_token}')

        # ── Login with correct credentials ───────────────────────────────────
        # OAuth2PasswordRequestForm uses 'username' field for the email
        response_4 = await integration_client.post('/api/v1/login', data={'username': 'a.kostenkouk@gmail.com',
                                                       'password': '12345678'})
        # ── Login with wrong password → 401 ─────────────────────────────────
        response_5 = await integration_client.post('/api/v1/login', data={'username': 'a.kostenkouk@gmail.com',
                                                       'password': 'anfjdjfdkdfj111111111111'})

        assert response_1.status_code == status.HTTP_201_CREATED
        assert response_2.status_code == status.HTTP_409_CONFLICT
        assert response_3.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response_4.status_code == status.HTTP_200_OK
        assert response_5.status_code == status.HTTP_401_UNAUTHORIZED
