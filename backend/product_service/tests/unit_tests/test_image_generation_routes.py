from fastapi import status
from httpx import AsyncClient
from uuid import uuid4

import pytest

from exceptions.image_generation_exceptions import (
    ImageGenerationJobNotFoundError,
    ImageGenerationLimitExceededError,
)
from tests.conftest import TEST_API
from shared.settings import get_settings
from tests.conftest import SIGNING_KEYS
from shared.testing.signing_keys import ANONYMOUS

settings = get_settings()

# The gateway asserts the caller through these headers; sending them exercises
# the real identity dependency rather than overriding it.
TEST_CALLER_ID = uuid4()
SIGNED_IN = SIGNING_KEYS.caller_auth(user_id=TEST_CALLER_ID, role="user")
ADMIN = SIGNING_KEYS.caller_auth(user_id=uuid4(), role=settings.SECRET_ROLE)


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
            auth=SIGNED_IN,
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        body = response.json()
        assert "job_id" in body
        assert body["status"] == "pending"
        assert body["remaining_generations"] == 2
        assert body["generation_limit"] == settings.PRODUCT_IMAGE_GENERATION_LIMIT

    async def test_anonymous_caller_is_rejected_before_quota_is_spent(
        self,
        client_for_unit_testing: AsyncClient,
        mock_route_image_generation_service,
    ):
        response = await client_for_unit_testing.post(
            f"{TEST_API}/images/generations",
            json=self._payload,
            auth=ANONYMOUS,
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_route_image_generation_service.submit_job.assert_not_called()
        client_for_unit_testing.app_mock_generate_image_task.kiq.assert_not_called()

    async def test_quota_and_job_belong_to_the_caller(
        self,
        client_for_unit_testing: AsyncClient,
        mock_route_image_generation_service,
    ):
        await client_for_unit_testing.post(
            f"{TEST_API}/images/generations",
            json=self._payload,
            auth=SIGNED_IN,
        )

        kwargs = mock_route_image_generation_service.submit_job.call_args.kwargs
        assert kwargs["user_id"] == TEST_CALLER_ID

    async def test_no_guest_cookie_is_set(
        self,
        client_for_unit_testing: AsyncClient,
    ):
        response = await client_for_unit_testing.post(
            f"{TEST_API}/images/generations",
            json=self._payload,
            auth=SIGNED_IN,
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.headers.get("set-cookie") is None

    async def test_limit_exceeded_returns_429_with_retry_after(
        self,
        client_for_unit_testing: AsyncClient,
        mock_route_image_generation_service,
    ):
        mock_route_image_generation_service.submit_job.side_effect = (
            ImageGenerationLimitExceededError(retry_after=3600, limit=10)
        )
        response = await client_for_unit_testing.post(
            f"{TEST_API}/images/generations",
            json=self._payload,
            auth=SIGNED_IN,
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert response.headers.get("retry-after") == "3600"
        client_for_unit_testing.app_mock_generate_image_task.kiq.assert_not_called()

    async def test_location_header_points_to_status_endpoint(
        self,
        client_for_unit_testing: AsyncClient,
    ):
        response = await client_for_unit_testing.post(
            f"{TEST_API}/images/generations",
            json=self._payload,
            auth=SIGNED_IN,
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
            auth=SIGNED_IN,
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        mock_task = client_for_unit_testing.app_mock_generate_image_task
        mock_task.kiq.assert_called_once()
        call_args = mock_task.kiq.call_args
        assert call_args.args[1] == self._payload["prompt"]
        assert call_args.args[2] == self._payload["style"]
        assert call_args.args[3] is False


class TestGenerationJobStatusEndpoint:
    async def test_returns_completed_job(
        self,
        client_for_unit_testing: AsyncClient,
        mock_route_image_generation_service,
    ):
        job_id = str(uuid4())
        response = await client_for_unit_testing.get(
            f"{TEST_API}/images/generations/{job_id}/status",
            auth=SIGNED_IN,
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["status"] == "completed"
        assert body["image_url"] == "/media/generated-designs/fake-image.png"
        assert body["design_asset"]["width_px"] == 4096
        assert body["job_id"] == job_id
        mock_route_image_generation_service.get_job.assert_awaited_once_with(
            job_id, user_id=TEST_CALLER_ID
        )

    async def test_anonymous_poll_is_rejected(
        self,
        client_for_unit_testing: AsyncClient,
    ):
        response = await client_for_unit_testing.get(
            f"{TEST_API}/images/generations/{uuid4()}/status",
            auth=ANONYMOUS,
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_unknown_job_returns_404(
        self,
        client_for_unit_testing: AsyncClient,
        mock_route_image_generation_service,
    ):
        mock_route_image_generation_service.get_job.side_effect = ImageGenerationJobNotFoundError()
        response = await client_for_unit_testing.get(
            f"{TEST_API}/images/generations/{uuid4()}/status",
            auth=SIGNED_IN,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAdminSchemaEndpoints:
    @pytest.mark.parametrize("resource", ["products", "categories", "images", "reviews"])
    async def test_admin_gets_schema(self, client_for_unit_testing: AsyncClient, resource: str):
        response = await client_for_unit_testing.get(
            f"{TEST_API}/admin/schema/{resource}", auth=ADMIN,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["fields"]

    @pytest.mark.parametrize("resource", ["products", "categories", "images", "reviews"])
    async def test_regular_user_is_forbidden(self, client_for_unit_testing: AsyncClient, resource: str):
        response = await client_for_unit_testing.get(
            f"{TEST_API}/admin/schema/{resource}", auth=SIGNED_IN,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize("resource", ["products", "categories", "images", "reviews"])
    async def test_anonymous_is_rejected(self, client_for_unit_testing: AsyncClient, resource: str):
        response = await client_for_unit_testing.get(f"{TEST_API}/admin/schema/{resource}", auth=ANONYMOUS)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
