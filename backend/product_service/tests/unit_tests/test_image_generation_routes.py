from fastapi import status
from httpx import AsyncClient
from uuid import uuid4

from exceptions.image_generation_exceptions import (
    ImageGenerationJobNotFoundError,
    ImageGenerationLimitExceededError,
)
from tests.conftest import TEST_API
from shared.shared_instances import settings


class TestGenerateImageEndpoint:
    _payload = {
        "prompt": "Cyberpunk tiger face with neon accents",
        "style": "Streetwear",
    }

    async def test_returns_202_with_job_id(
        self,
        client_for_unit_testing: AsyncClient,
    ):
        response = await client_for_unit_testing.post(
            f"{TEST_API}/images/generations",
            json=self._payload,
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        body = response.json()
        assert "job_id" in body
        assert body["status"] == "pending"

    async def test_guest_generation_sets_guest_cookie(
        self,
        client_for_unit_testing: AsyncClient,
    ):
        response = await client_for_unit_testing.post(
            f"{TEST_API}/images/generations",
            json=self._payload,
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json()["remaining_generations"] == 2
        assert f"{settings.GUEST_QUOTA_COOKIE}=" in response.headers.get("set-cookie", "")

    async def test_existing_guest_cookie_reused_without_setting_new_cookie(
        self,
        client_for_unit_testing: AsyncClient,
    ):
        guest_id = str(uuid4())
        client_for_unit_testing.cookies.set(settings.GUEST_QUOTA_COOKIE, guest_id)
        response = await client_for_unit_testing.post(
            f"{TEST_API}/images/generations",
            json=self._payload,
        )
        client_for_unit_testing.cookies.delete(settings.GUEST_QUOTA_COOKIE)

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json()["guest_limit"] == 3
        assert response.headers.get("set-cookie") is None

    async def test_guest_limit_exceeded_returns_429(
        self,
        client_for_unit_testing: AsyncClient,
        mock_route_image_generation_service,
    ):
        mock_route_image_generation_service.submit_job.side_effect = (
            ImageGenerationLimitExceededError(retry_after=3600, limit=3)
        )
        guest_id = str(uuid4())
        client_for_unit_testing.cookies.set(settings.GUEST_QUOTA_COOKIE, guest_id)
        response = await client_for_unit_testing.post(
            f"{TEST_API}/images/generations",
            json=self._payload,
        )
        client_for_unit_testing.cookies.delete(settings.GUEST_QUOTA_COOKIE)

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
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert f"{settings.GUEST_QUOTA_COOKIE}=" in set_cookie_header
        assert "Secure" not in set_cookie_header

    async def test_location_header_points_to_status_endpoint(
        self,
        client_for_unit_testing: AsyncClient,
    ):
        response = await client_for_unit_testing.post(
            f"{TEST_API}/images/generations",
            json=self._payload,
            follow_redirects=False,
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        location = response.headers.get("location", "")
        assert "/images/generations/" in location
        assert location.endswith("/status")

    async def test_dispatches_task_via_kiq(
        self,
        client_for_unit_testing: AsyncClient,
    ):
        response = await client_for_unit_testing.post(
            f"{TEST_API}/images/generations",
            json=self._payload,
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_task = client_for_unit_testing.app_mock_generate_image_task
        mock_task.kiq.assert_called_once()
        call_args = mock_task.kiq.call_args
        assert call_args.args[1] == self._payload["prompt"]
        assert call_args.args[2] == self._payload["style"]
        assert call_args.args[3] is False


    async def test_returns_completed_job(
        self,
        client_for_unit_testing: AsyncClient,
    ):
        job_id = str(uuid4())
        response = await client_for_unit_testing.get(
            f"{TEST_API}/images/generations/{job_id}/status",
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["status"] == "completed"
        assert body["image_url"] == "/media/generated/fake-image.png"
        assert body["job_id"] == job_id

    async def test_unknown_job_returns_404(
        self,
        client_for_unit_testing: AsyncClient,
        mock_route_image_generation_service,
    ):
        mock_route_image_generation_service.get_job.side_effect = ImageGenerationJobNotFoundError()
        response = await client_for_unit_testing.get(
            f"{TEST_API}/images/generations/{uuid4()}/status",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
