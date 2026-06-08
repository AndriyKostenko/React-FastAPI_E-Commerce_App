import base64
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from exceptions.image_generation_exceptions import ImageGenerationProviderError
from service_layer.image_generation_service import ImageGenerationService


class _FakeResponse:
    def __init__(self, status: int, body: dict):
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self) -> str:
        return json.dumps(self._body)


class _FakeSession:
    def __init__(self, response: _FakeResponse, request_log: dict):
        self._response = response
        self._request_log = request_log

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, endpoint: str, headers: dict, json: dict):
        self._request_log["endpoint"] = endpoint
        self._request_log["headers"] = headers
        self._request_log["payload"] = json
        return self._response


@pytest.fixture
def image_generation_settings() -> MagicMock:
    settings = MagicMock()
    settings.OPENROUTER_API_KEY = "test-key"
    settings.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    settings.OPENROUTER_IMAGE_MODEL = "openai/gpt-5-image-mini"
    settings.OPENROUTER_IMAGE_SIZE = "0.5K"
    settings.OPENROUTER_IMAGE_ASPECT_RATIO = "1:1"
    settings.PRODUCT_IMAGE_GUEST_GENERATION_LIMIT = 3
    settings.PRODUCT_IMAGE_REGISTERED_GENERATION_LIMIT = 10
    settings.PRODUCT_IMAGE_GUEST_GENERATION_WINDOW_HOURS = 24
    settings.GUEST_QUOTA_COOKIE = "guest_generation_id"
    settings.FRONTEND_URL = "https://example.com"
    return settings


@pytest.fixture
def image_generation_cache_manager() -> MagicMock:
    redis = MagicMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.ttl = AsyncMock(return_value=3600)

    cache_manager = MagicMock()
    cache_manager.service_prefix = "product-service"
    cache_manager.redis = redis
    return cache_manager


@pytest.fixture
def image_generation_service_unit(
    image_generation_settings: MagicMock, image_generation_cache_manager: MagicMock
) -> ImageGenerationService:
    logger = MagicMock()
    return ImageGenerationService(
        settings=image_generation_settings,
        cache_manager=image_generation_cache_manager,
        logger=logger,
    )


class TestGenerateImage:
    async def test_uses_chat_completions_and_returns_saved_image_path(
        self,
        image_generation_service_unit: ImageGenerationService,
    ) -> None:
        request_log: dict = {}
        response_body = {
            "choices": [
                {
                    "message": {
                        "images": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "data:image/png;base64,aGVsbG8=",
                                },
                            }
                        ]
                    }
                }
            ]
        }
        fake_session = _FakeSession(_FakeResponse(status=200, body=response_body), request_log)
        image_generation_service_unit.save_image = AsyncMock(
            return_value="/media/generated/fake-image.png"
        )

        with patch(
            "service_layer.image_generation_service.ClientSession",
            return_value=fake_session,
        ):
            result = await image_generation_service_unit.generate_image(
                prompt="Cyberpunk tiger face with neon accents",
                style="Streetwear",
                is_guest_user=True,
                guest_id=str(uuid4()),
                remove_background=True,
            )

        assert request_log["endpoint"] == "https://openrouter.ai/api/v1/chat/completions"
        assert request_log["payload"]["model"] == "google/gemini-3.1-flash-image-preview"
        assert request_log["payload"]["modalities"] == ["image", "text"]
        assert "image_config" not in request_log["payload"]
        assert request_log["payload"]["stream"] is False
        assert request_log["payload"]["messages"][0]["role"] == "user"
        assert "Style reference: Streetwear" in request_log["payload"]["messages"][0]["content"]
        assert "Remove the background completely" in request_log["payload"]["messages"][0]["content"]
        assert request_log["headers"]["X-OpenRouter-Title"] == "react-fastapi-ecommerce"
        image_generation_service_unit.save_image.assert_awaited_once_with(
            "data:image/png;base64,aGVsbG8="
        )
        assert result.image_url == "/media/generated/fake-image.png"
        assert result.model == "google/gemini-3.1-flash-image-preview"
        assert result.remaining_generations == 2

    async def test_raises_when_provider_returns_no_images(
        self,
        image_generation_service_unit: ImageGenerationService,
    ) -> None:
        request_log: dict = {}
        response_body = {"choices": [{"message": {"content": "No image available"}}]}
        fake_session = _FakeSession(_FakeResponse(status=200, body=response_body), request_log)

        with patch(
            "service_layer.image_generation_service.ClientSession",
            return_value=fake_session,
        ):
            with pytest.raises(ImageGenerationProviderError, match="No image returned from provider"):
                await image_generation_service_unit.generate_image(
                    prompt="Create a neon logo",
                    style="Streetwear",
                    is_guest_user=False,
                    user_id=str(uuid4()),
                )


class TestSaveImage:
    async def test_saves_data_url_image_to_media_generated(
        self,
        image_generation_service_unit: ImageGenerationService,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
        image_bytes = b"sample-image-bytes"
        payload = "data:image/png;base64," + base64.b64encode(image_bytes).decode("utf-8")

        saved_url = await image_generation_service_unit.save_image(payload)

        saved_file = tmp_path / "generated" / saved_url.rsplit("/", 1)[-1]
        assert saved_url.startswith("/media/generated/")
        assert saved_file.exists()
        assert saved_file.read_bytes() == image_bytes
