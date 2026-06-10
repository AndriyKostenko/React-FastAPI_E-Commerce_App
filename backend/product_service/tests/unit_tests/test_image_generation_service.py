import base64
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from exceptions.image_generation_exceptions import (
    ImageGenerationLimitExceededError,
    ImageGenerationProviderError,
)
from service_layer.image_generation_service import ImageGenerationService
from service_layer.image_generation_quota import GenerationQuotaService
from service_layer.image_job_store import ImageJobStore
from service_layer.openrouter_client import OpenRouterClient
from service_layer.image_storage_service import ImageStorageService


# ── shared fake HTTP machinery ─────────────────────────────────────────────────

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

    def post(self, endpoint: str, headers: dict, json: dict):
        self._request_log["endpoint"] = endpoint
        self._request_log["headers"] = headers
        self._request_log["payload"] = json
        return self._response


# ── shared fixtures ────────────────────────────────────────────────────────────

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
    settings.WEBSITE_NAME = "react-fastapi-ecommerce"
    return settings


@pytest.fixture
def mock_redis() -> MagicMock:
    redis = MagicMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.ttl = AsyncMock(return_value=3600)
    redis.setex = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    return redis


@pytest.fixture
def mock_cache_manager(mock_redis: MagicMock) -> MagicMock:
    cache_manager = MagicMock()
    cache_manager.service_prefix = "product-service"
    cache_manager.redis = mock_redis
    return cache_manager


@pytest.fixture
def quota_service(
    image_generation_settings: MagicMock, mock_cache_manager: MagicMock
) -> GenerationQuotaService:
    return GenerationQuotaService(
        cache_manager=mock_cache_manager,
        settings=image_generation_settings,
        logger=MagicMock(),
    )


@pytest.fixture
def job_store(mock_cache_manager: MagicMock) -> ImageJobStore:
    return ImageJobStore(
        cache_manager=mock_cache_manager,
        logger=MagicMock(),
    )


@pytest.fixture
def storage_service() -> ImageStorageService:
    return ImageStorageService(logger=MagicMock())


@pytest.fixture
def image_generation_service_unit(
    image_generation_settings: MagicMock,
) -> ImageGenerationService:
    """ImageGenerationService wired with fully mocked collaborators."""
    return ImageGenerationService(
        quota_service=MagicMock(spec=GenerationQuotaService),
        job_store=MagicMock(spec=ImageJobStore),
        openrouter_client=MagicMock(spec=OpenRouterClient),
        storage_service=MagicMock(spec=ImageStorageService),
        settings=image_generation_settings,
        logger=MagicMock(),
    )


# ── OpenRouterClient ───────────────────────────────────────────────────────────

class TestOpenRouterClient:
    def _make_client(
        self, settings: MagicMock, fake_session: _FakeSession
    ) -> OpenRouterClient:
        return OpenRouterClient(session=fake_session, settings=settings, logger=MagicMock())

    def _success_body(self) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "images": [
                            {"type": "image_url", "image_url": {"url": "data:image/png;base64,aGVsbG8="}}
                        ]
                    }
                }
            ]
        }

    async def test_posts_to_chat_completions_endpoint(
        self, image_generation_settings: MagicMock
    ) -> None:
        log: dict = {}
        client = self._make_client(
            image_generation_settings,
            _FakeSession(_FakeResponse(200, self._success_body()), log),
        )
        await client.generate(prompt="Tiger", style="Streetwear")
        assert log["endpoint"] == "https://openrouter.ai/api/v1/chat/completions"

    async def test_payload_model_and_modalities_for_non_google_model(
        self, image_generation_settings: MagicMock
    ) -> None:
        log: dict = {}
        client = self._make_client(
            image_generation_settings,
            _FakeSession(_FakeResponse(200, self._success_body()), log),
        )
        await client.generate(prompt="Tiger", style="Streetwear")
        assert log["payload"]["model"] == "openai/gpt-5-image-mini"
        assert log["payload"]["modalities"] == ["image"]
        assert log["payload"]["stream"] is False

    async def test_payload_includes_image_config_for_non_google_model(
        self, image_generation_settings: MagicMock
    ) -> None:
        log: dict = {}
        client = self._make_client(
            image_generation_settings,
            _FakeSession(_FakeResponse(200, self._success_body()), log),
        )
        await client.generate(prompt="Tiger", style="Streetwear")
        cfg = log["payload"]["image_config"]
        assert cfg["aspect_ratio"] == "1:1"
        assert cfg["image_size"] == "0.5K"
        assert cfg["num_inference_steps"] == 4
        assert cfg["response_format"] == "b64_json"

    async def test_remove_background_appended_to_prompt(
        self, image_generation_settings: MagicMock
    ) -> None:
        log: dict = {}
        client = self._make_client(
            image_generation_settings,
            _FakeSession(_FakeResponse(200, self._success_body()), log),
        )
        await client.generate(prompt="Tiger", style="Streetwear", remove_background=True)
        content = log["payload"]["messages"][0]["content"]
        assert "Style reference: Streetwear" in content
        assert "Remove the background completely" in content

    async def test_authorization_and_title_headers(
        self, image_generation_settings: MagicMock
    ) -> None:
        log: dict = {}
        client = self._make_client(
            image_generation_settings,
            _FakeSession(_FakeResponse(200, self._success_body()), log),
        )
        await client.generate(prompt="Tiger", style="Neon")
        assert log["headers"]["Authorization"] == "Bearer test-key"
        assert log["headers"]["X-OpenRouter-Title"] == "react-fastapi-ecommerce"

    async def test_returns_image_payload_and_model_name(
        self, image_generation_settings: MagicMock
    ) -> None:
        log: dict = {}
        client = self._make_client(
            image_generation_settings,
            _FakeSession(_FakeResponse(200, self._success_body()), log),
        )
        payload, model = await client.generate(prompt="Tiger", style="Neon")
        assert payload == "data:image/png;base64,aGVsbG8="
        assert model == "openai/gpt-5-image-mini"

    async def test_raises_when_provider_returns_no_images(
        self, image_generation_settings: MagicMock
    ) -> None:
        log: dict = {}
        body = {"choices": [{"message": {"content": "No image available"}}]}
        client = self._make_client(
            image_generation_settings, _FakeSession(_FakeResponse(200, body), log)
        )
        with pytest.raises(ImageGenerationProviderError, match="No image returned from provider"):
            await client.generate(prompt="Logo", style="Modern")

    async def test_raises_on_http_error_status(
        self, image_generation_settings: MagicMock
    ) -> None:
        log: dict = {}
        client = self._make_client(
            image_generation_settings,
            _FakeSession(_FakeResponse(429, {"error": "rate limit"}), log),
        )
        with pytest.raises(ImageGenerationProviderError, match="status 429"):
            await client.generate(prompt="Logo", style="Modern")

    async def test_google_model_uses_text_and_image_modalities(
        self, image_generation_settings: MagicMock
    ) -> None:
        image_generation_settings.OPENROUTER_IMAGE_MODEL = "google/gemini-3.1-flash-image-preview"
        image_generation_settings.OPENROUTER_IMAGE_SIZE = ""
        image_generation_settings.OPENROUTER_IMAGE_ASPECT_RATIO = ""
        log: dict = {}
        client = self._make_client(
            image_generation_settings,
            _FakeSession(_FakeResponse(200, self._success_body()), log),
        )
        await client.generate(prompt="Tiger", style="Neon")
        assert log["payload"]["modalities"] == ["image", "text"]
        # Google model with no explicit size falls back to the "0.5K" default
        assert log["payload"]["image_config"] == {"image_size": "0.5K"}
        # diffusion-only params must not appear for Google models
        assert "num_inference_steps" not in log["payload"].get("image_config", {})


# ── ImageStorageService ────────────────────────────────────────────────────────

class TestImageStorageService:
    async def test_saves_data_url_image_to_media_generated(
        self,
        storage_service: ImageStorageService,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
        image_bytes = b"sample-image-bytes"
        payload = "data:image/png;base64," + base64.b64encode(image_bytes).decode("utf-8")

        saved_url = await storage_service.save(payload)

        saved_file = tmp_path / "generated" / saved_url.rsplit("/", 1)[-1]
        assert saved_url.startswith("/media/generated/")
        assert saved_file.exists()
        assert saved_file.read_bytes() == image_bytes

    async def test_saves_plain_base64_without_data_url_prefix(
        self,
        storage_service: ImageStorageService,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
        image_bytes = b"plain-bytes"
        payload = base64.b64encode(image_bytes).decode("utf-8")

        saved_url = await storage_service.save(payload)

        saved_file = tmp_path / "generated" / saved_url.rsplit("/", 1)[-1]
        assert saved_file.read_bytes() == image_bytes

    async def test_raises_on_invalid_base64(
        self,
        storage_service: ImageStorageService,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
        with pytest.raises(ImageGenerationProviderError):
            await storage_service.save("data:image/png;base64,!!!not-valid!!!")


# ── GenerationQuotaService ─────────────────────────────────────────────────────

class TestGenerationQuotaService:
    async def test_returns_remaining_on_first_use(
        self, quota_service: GenerationQuotaService, mock_redis: MagicMock
    ) -> None:
        mock_redis.incr = AsyncMock(return_value=1)  # first use
        remaining = await quota_service.consume("user-abc", is_guest=True)
        assert remaining == 2  # limit=3, used=1

    async def test_sets_ttl_on_first_use(
        self, quota_service: GenerationQuotaService, mock_redis: MagicMock
    ) -> None:
        mock_redis.incr = AsyncMock(return_value=1)
        await quota_service.consume("user-abc", is_guest=True)
        mock_redis.expire.assert_awaited_once()

    async def test_raises_when_limit_exceeded(
        self, quota_service: GenerationQuotaService, mock_redis: MagicMock
    ) -> None:
        mock_redis.incr = AsyncMock(return_value=4)  # over guest limit of 3
        with pytest.raises(ImageGenerationLimitExceededError):
            await quota_service.consume("user-abc", is_guest=True)

    async def test_registered_user_uses_higher_limit(
        self, quota_service: GenerationQuotaService, mock_redis: MagicMock
    ) -> None:
        mock_redis.incr = AsyncMock(return_value=10)  # registered limit=10, exactly at limit
        remaining = await quota_service.consume("user-xyz", is_guest=False)
        assert remaining == 0

    async def test_quota_key_namespaced_by_user_type(
        self, quota_service: GenerationQuotaService, mock_redis: MagicMock
    ) -> None:
        await quota_service.consume("user-abc", is_guest=True)
        key_used = mock_redis.incr.call_args[0][0]
        assert "guest" in key_used
        assert "user-abc" in key_used


# ── ImageJobStore ──────────────────────────────────────────────────────────────

class TestImageJobStore:
    async def test_create_writes_pending_status(
        self, job_store: ImageJobStore, mock_redis: MagicMock
    ) -> None:
        from orjson import loads
        await job_store.create("job-1")
        raw = mock_redis.setex.call_args.kwargs["value"]
        data = loads(raw)
        assert data["status"] == "pending"
        assert "submitted_at" in data

    async def test_set_state_writes_given_status(
        self, job_store: ImageJobStore, mock_redis: MagicMock
    ) -> None:
        from orjson import loads
        await job_store.set_state("job-1", "completed", {"image_url": "/media/out.png"})
        raw = mock_redis.setex.call_args.kwargs["value"]
        data = loads(raw)
        assert data["status"] == "completed"
        assert data["image_url"] == "/media/out.png"

    async def test_get_returns_parsed_dict(
        self, job_store: ImageJobStore, mock_redis: MagicMock
    ) -> None:
        from orjson import dumps
        mock_redis.get = AsyncMock(return_value=dumps({"status": "running"}))
        result = await job_store.get("job-1")
        assert result["status"] == "running"

    async def test_get_raises_when_job_not_found(
        self, job_store: ImageJobStore, mock_redis: MagicMock
    ) -> None:
        from exceptions.image_generation_exceptions import ImageGenerationJobNotFoundError
        mock_redis.get = AsyncMock(return_value=None)
        with pytest.raises(ImageGenerationJobNotFoundError):
            await job_store.get("missing-job")


# ── ImageGenerationService (orchestrator) ─────────────────────────────────────

class TestImageGenerationService:
    async def test_generate_image_delegates_to_collaborators(
        self, image_generation_service_unit: ImageGenerationService
    ) -> None:
        image_generation_service_unit._quota_service.consume = AsyncMock(return_value=2)
        image_generation_service_unit._openrouter_client.generate = AsyncMock(
            return_value=("data:image/png;base64,aGVsbG8=", "openai/gpt-5-image-mini")
        )
        image_generation_service_unit._storage_service.save = AsyncMock(
            return_value="/media/generated/out.png"
        )

        result = await image_generation_service_unit.generate_image(
            prompt="Cyberpunk tiger",
            style="Streetwear",
            is_guest_user=True,
            guest_id=str(uuid4()),
        )

        assert result.image_url == "/media/generated/out.png"
        assert result.model == "openai/gpt-5-image-mini"
        assert result.remaining_generations == 2
        assert result.guest_limit == 3

    async def test_generate_image_raises_without_guest_id(
        self, image_generation_service_unit: ImageGenerationService
    ) -> None:
        with pytest.raises(ImageGenerationProviderError):
            await image_generation_service_unit.generate_image(
                prompt="Tiger", style="Neon", is_guest_user=True, guest_id=None
            )

    async def test_submit_job_consumes_quota_and_creates_job(
        self, image_generation_service_unit: ImageGenerationService
    ) -> None:
        image_generation_service_unit._quota_service.consume = AsyncMock(return_value=1)
        image_generation_service_unit._job_store.create = AsyncMock()

        remaining = await image_generation_service_unit.submit_job(
            job_id="job-123",
            prompt="Logo",
            style="Modern",
            is_guest_user=False,
            user_id=str(uuid4()),
        )

        assert remaining == 1
        image_generation_service_unit._job_store.create.assert_awaited_once_with("job-123")

    async def test_run_job_sets_running_then_completed(
        self, image_generation_service_unit: ImageGenerationService
    ) -> None:
        image_generation_service_unit._openrouter_client.generate = AsyncMock(
            return_value=("data:image/png;base64,aGVsbG8=", "openai/gpt-5-image-mini")
        )
        image_generation_service_unit._storage_service.save = AsyncMock(
            return_value="/media/generated/out.png"
        )
        image_generation_service_unit._job_store.set_state = AsyncMock()

        await image_generation_service_unit.run_job("job-123", "Tiger", "Neon")

        calls = image_generation_service_unit._job_store.set_state.call_args_list
        assert calls[0].args == ("job-123", "running")
        assert calls[1].args[1] == "completed"
        assert calls[1].args[2]["image_url"] == "/media/generated/out.png"

    async def test_run_job_sets_failed_on_exception(
        self, image_generation_service_unit: ImageGenerationService
    ) -> None:
        image_generation_service_unit._openrouter_client.generate = AsyncMock(
            side_effect=ImageGenerationProviderError("provider down")
        )
        image_generation_service_unit._job_store.set_state = AsyncMock()

        await image_generation_service_unit.run_job("job-456", "Tiger", "Neon")

        last_call = image_generation_service_unit._job_store.set_state.call_args_list[-1]
        assert last_call.args[1] == "failed"

    async def test_save_image_delegates_to_storage_service(
        self, image_generation_service_unit: ImageGenerationService
    ) -> None:
        image_generation_service_unit._storage_service.save = AsyncMock(
            return_value="/media/generated/test.png"
        )
        result = await image_generation_service_unit.save_image("data:image/png;base64,aGVsbG8=")
        assert result == "/media/generated/test.png"
