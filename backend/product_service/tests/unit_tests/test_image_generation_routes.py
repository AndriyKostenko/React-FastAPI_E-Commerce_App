from fastapi import status
from httpx import AsyncClient

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
            cookies={"guest_generation_id": "existing-guest-id"},
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
            cookies={"guest_generation_id": "existing-guest-id"},
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
