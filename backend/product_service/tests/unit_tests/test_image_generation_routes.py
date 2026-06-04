from fastapi import status
from httpx import AsyncClient
from uuid import uuid4

from exceptions.image_generation_exceptions import ImageGenerationLimitExceededError
from tests.conftest import TEST_API


class TestGenerateImageEndpoint:
    _payload = {
        "prompt": "Cyberpunk tiger face with neon accents",
        "style": "Streetwear",
    }

    async def test_guest_generation_sets_guest_cookie(
        self,
        client_for_unit_testing: AsyncClient,
    ):
        response = await client_for_unit_testing.post(
            f"{TEST_API}/images/generations",
            json=self._payload,
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["remaining_generations"] == 2
        assert "guest_generation_id=" in response.headers.get("set-cookie", "")

    async def test_existing_guest_cookie_reused_without_setting_new_cookie(
        self,
        client_for_unit_testing: AsyncClient,
    ):
        response = await client_for_unit_testing.post(
            f"{TEST_API}/images/generations",
            json=self._payload,
            cookies={"guest_generation_id": str(uuid4())},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["guest_limit"] == 3
        assert response.headers.get("set-cookie") is None

    async def test_guest_limit_exceeded_returns_429(
        self,
        client_for_unit_testing: AsyncClient,
        mock_route_image_generation_service,
    ):
        mock_route_image_generation_service.generate_image.side_effect = (
            ImageGenerationLimitExceededError(retry_after=3600, limit=3)
        )
        response = await client_for_unit_testing.post(
            f"{TEST_API}/images/generations",
            json=self._payload,
            cookies={"guest_generation_id": str(uuid4())},
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    async def test_guest_cookie_not_marked_secure_on_http(
        self,
        client_for_unit_testing: AsyncClient,
        mock_route_image_generation_service,
    ):
        mock_route_image_generation_service.settings.SECURE_COOKIES = True
        response = await client_for_unit_testing.post(
            f"{TEST_API}/images/generations",
            json=self._payload,
        )

        set_cookie_header = response.headers.get("set-cookie", "")
        assert response.status_code == status.HTTP_201_CREATED
        assert "guest_generation_id=" in set_cookie_header
        assert "Secure" not in set_cookie_header
