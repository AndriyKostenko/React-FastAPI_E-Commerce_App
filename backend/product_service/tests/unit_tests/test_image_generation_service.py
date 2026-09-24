import base64
import io
import json
from pathlib import Path
from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import SecretStr
from PIL import Image

from exceptions.image_generation_exceptions import (
    ImageBackgroundRemovalError,
    ImageGenerationLimitExceededError,
    ImageGenerationProviderError,
)
from service_layer.background_removal_service import BackgroundRemover
from service_layer.image_generation_service import ImageGenerationService
from service_layer.image_generation_quota import GenerationQuotaService
from service_layer.image_job_store import ImageJobStore
from service_layer.openrouter_client import OpenRouterClient
from service_layer.image_storage_service import ImageStorageService, StoredImage
from shared.contracts.artwork import GeneratedArtworkAsset


def _asset() -> GeneratedArtworkAsset:
    return GeneratedArtworkAsset(
        key="generated-designs/2026/08/" + "a" * 32 + ".png",
        width_px=4096,
        height_px=4096,
        embedded_dpi=300,
        sha256="b" * 64,
        token="c" * 43,
    )


def _png_payload(width: int = 20, height: int = 24) -> str:
    output = io.BytesIO()
    Image.new("RGBA", (width, height), (20, 40, 60, 0)).save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


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
    settings.OPENROUTER_API_KEY = SecretStr("test-key")
    # The client reads the unwrapping accessor, not the raw field, so the
    # double has to answer that too.
    settings.OPENROUTER_KEY = "test-key"
    settings.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    settings.OPENROUTER_IMAGE_MODEL = "openai/gpt-5-image-mini"
    settings.OPENROUTER_IMAGE_SIZE = "0.5K"
    settings.PRINT_IMAGE_GENERATION_SIZE = "4K"
    settings.OPENROUTER_IMAGE_ASPECT_RATIO = "1:1"
    settings.PRODUCT_IMAGE_GENERATION_LIMIT = 3
    settings.PRODUCT_IMAGE_GENERATION_WINDOW_HOURS = 24
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
def artwork_storage_settings(tmp_path: Path) -> MagicMock:
    settings = MagicMock()
    settings.ARTWORK_STORAGE_BACKEND = "local"
    settings.AWS_S3_ARTWORK_BUCKET = None
    settings.MEDIA_ROOT = str(tmp_path)
    settings.PRINT_IMAGE_MIN_WIDTH_PX = 10
    settings.PRINT_IMAGE_MIN_HEIGHT_PX = 10
    settings.PRINT_IMAGE_MAX_DIMENSION_PX = 100
    settings.PRINT_IMAGE_MAX_PIXELS = 10_000
    settings.PRINT_IMAGE_MAX_BYTES = 1_000_000
    settings.PRINT_IMAGE_EMBEDDED_DPI = 300
    settings.ARTWORK_SIGNING_KEY = "test-signing-secret"
    settings.AWS_S3_KMS_KEY_ID = None
    settings.AWS_S3_PUBLIC_BASE_URL = None
    settings.AWS_S3_PRESIGNED_URL_TTL_SECONDS = 3600
    return settings


@pytest.fixture
def storage_service(artwork_storage_settings: MagicMock) -> ImageStorageService:
    return ImageStorageService(
        logger=MagicMock(), settings=artwork_storage_settings
    )


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
        background_remover=MagicMock(spec=BackgroundRemover),
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
        assert cfg["image_size"] == "4K"
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
        assert "plain, flat, uniform background" in content
        assert log["payload"]["image_config"]["background"] == "transparent"
        assert log["payload"]["image_config"]["output_format"] == "png"

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
        image_generation_settings.PRINT_IMAGE_GENERATION_SIZE = ""
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
        payload = _png_payload()

        stored = await storage_service.save(payload)

        saved_file = tmp_path / stored.asset.key
        assert stored.image_url.startswith("/media/generated-designs/")
        assert saved_file.exists()
        with Image.open(saved_file) as image:
            assert image.size == (20, 24)
            assert image.mode == "RGBA"
        assert stored.asset.width_px == 20
        assert stored.asset.height_px == 24

    async def test_saves_plain_base64_without_data_url_prefix(
        self,
        storage_service: ImageStorageService,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        payload = _png_payload().partition(",")[2]

        stored = await storage_service.save(payload)

        assert (tmp_path / stored.asset.key).exists()

    async def test_raises_on_invalid_base64(
        self,
        storage_service: ImageStorageService,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(ImageGenerationProviderError):
            await storage_service.save("data:image/png;base64,!!!not-valid!!!")

    async def test_rejects_valid_but_too_small_artwork(
        self, storage_service: ImageStorageService
    ) -> None:
        with pytest.raises(ImageGenerationProviderError, match="too small"):
            await storage_service.save(_png_payload(5, 5))

    async def test_s3_upload_is_private_encrypted_and_checksummed(
        self, artwork_storage_settings: MagicMock
    ) -> None:
        artwork_storage_settings.ARTWORK_STORAGE_BACKEND = "s3"
        artwork_storage_settings.AWS_S3_ARTWORK_BUCKET = "print-artwork"
        s3 = MagicMock()
        s3.generate_presigned_url.return_value = "https://signed.example/artwork"
        service = ImageStorageService(
            logger=MagicMock(), settings=artwork_storage_settings, s3_client=s3
        )

        stored = await service.save(_png_payload())

        request = s3.put_object.call_args.kwargs
        assert request["Bucket"] == "print-artwork"
        assert request["Key"] == stored.asset.key
        assert request["ContentType"] == "image/png"
        assert request["ServerSideEncryption"] == "AES256"
        assert request["ChecksumSHA256"]
        assert "ACL" not in request
        assert request["Metadata"]["width-px"] == "20"
        assert stored.image_url == "https://signed.example/artwork"


# ── GenerationQuotaService ─────────────────────────────────────────────────────

class TestGenerationQuotaService:
    async def test_returns_remaining_on_first_use(
        self, quota_service: GenerationQuotaService, mock_redis: MagicMock
    ) -> None:
        mock_redis.incr = AsyncMock(return_value=1)  # first use
        remaining = await quota_service.consume(uuid4())
        assert remaining == 2  # limit=3, used=1

    async def test_sets_ttl_on_first_use(
        self, quota_service: GenerationQuotaService, mock_redis: MagicMock
    ) -> None:
        mock_redis.incr = AsyncMock(return_value=1)
        await quota_service.consume(uuid4())
        mock_redis.expire.assert_awaited_once_with(ANY, 24 * 3600)

    async def test_exactly_at_limit_is_allowed(
        self, quota_service: GenerationQuotaService, mock_redis: MagicMock
    ) -> None:
        mock_redis.incr = AsyncMock(return_value=3)
        assert await quota_service.consume(uuid4()) == 0

    async def test_raises_when_limit_exceeded(
        self, quota_service: GenerationQuotaService, mock_redis: MagicMock
    ) -> None:
        mock_redis.incr = AsyncMock(return_value=4)  # over the limit of 3
        with pytest.raises(ImageGenerationLimitExceededError):
            await quota_service.consume(uuid4())

    async def test_quota_key_is_per_user(
        self, quota_service: GenerationQuotaService, mock_redis: MagicMock
    ) -> None:
        user_id = uuid4()
        await quota_service.consume(user_id)
        key_used = mock_redis.incr.call_args[0][0]
        assert key_used == f"product-service:image-generation:user:{user_id}"


# ── ImageJobStore ──────────────────────────────────────────────────────────────

class TestImageJobStore:
    async def test_create_writes_pending_status_and_owner(
        self, job_store: ImageJobStore, mock_redis: MagicMock
    ) -> None:
        from orjson import loads
        owner_id = uuid4()
        pipe = MagicMock()
        pipe.execute = AsyncMock(return_value=[True, True])
        mock_redis.pipeline = MagicMock(return_value=pipe)

        await job_store.create("job-1", owner_id=owner_id)

        job_call, owner_call = pipe.setex.call_args_list
        data = loads(job_call.kwargs["value"])
        assert data["status"] == "pending"
        assert "submitted_at" in data
        assert owner_call.kwargs["name"].endswith("image-job-owner:job-1")
        assert owner_call.kwargs["value"] == str(owner_id)
        pipe.execute.assert_awaited_once()

    async def test_set_state_writes_given_status(
        self, job_store: ImageJobStore, mock_redis: MagicMock
    ) -> None:
        from orjson import loads
        await job_store.set_state("job-1", "completed", {"image_url": "/media/out.png"})
        raw = mock_redis.setex.call_args.kwargs["value"]
        data = loads(raw)
        assert data["status"] == "completed"
        assert data["image_url"] == "/media/out.png"

    async def test_owner_gets_parsed_dict(
        self, job_store: ImageJobStore, mock_redis: MagicMock
    ) -> None:
        from orjson import dumps
        owner_id = uuid4()
        mock_redis.get = AsyncMock(side_effect=[str(owner_id).encode(), dumps({"status": "running"})])
        result = await job_store.get("job-1", owner_id=owner_id)
        assert result["status"] == "running"

    async def test_other_users_job_is_reported_missing(
        self, job_store: ImageJobStore, mock_redis: MagicMock
    ) -> None:
        from orjson import dumps
        from exceptions.image_generation_exceptions import ImageGenerationJobNotFoundError
        mock_redis.get = AsyncMock(side_effect=[str(uuid4()).encode(), dumps({"status": "completed"})])
        with pytest.raises(ImageGenerationJobNotFoundError):
            await job_store.get("job-1", owner_id=uuid4())

    async def test_get_raises_when_job_not_found(
        self, job_store: ImageJobStore, mock_redis: MagicMock
    ) -> None:
        from exceptions.image_generation_exceptions import ImageGenerationJobNotFoundError
        mock_redis.get = AsyncMock(return_value=None)
        with pytest.raises(ImageGenerationJobNotFoundError):
            await job_store.get("missing-job", owner_id=uuid4())


# ── ImageGenerationService (orchestrator) ─────────────────────────────────────

class TestImageGenerationService:
    async def test_generate_image_delegates_to_collaborators(
        self, image_generation_service_unit: ImageGenerationService
    ) -> None:
        user_id = uuid4()
        image_generation_service_unit._quota_service.consume = AsyncMock(return_value=2)
        image_generation_service_unit._openrouter_client.generate = AsyncMock(
            return_value=("data:image/png;base64,aGVsbG8=", "openai/gpt-5-image-mini")
        )
        image_generation_service_unit._storage_service.save = AsyncMock(
            return_value=StoredImage("/media/generated-designs/out.png", _asset())
        )

        result = await image_generation_service_unit.generate_image(
            prompt="Cyberpunk tiger",
            style="Streetwear",
            user_id=user_id,
        )

        image_generation_service_unit._quota_service.consume.assert_awaited_once_with(user_id)
        assert result.image_url == "/media/generated-designs/out.png"
        assert result.design_asset == _asset()
        assert result.model == "openai/gpt-5-image-mini"
        assert result.remaining_generations == 2
        assert result.generation_limit == 3

    async def test_submit_job_consumes_quota_and_creates_owned_job(
        self, image_generation_service_unit: ImageGenerationService
    ) -> None:
        user_id = uuid4()
        image_generation_service_unit._quota_service.consume = AsyncMock(return_value=1)
        image_generation_service_unit._job_store.create = AsyncMock()

        remaining = await image_generation_service_unit.submit_job(job_id="job-123", user_id=user_id)

        assert remaining == 1
        image_generation_service_unit._quota_service.consume.assert_awaited_once_with(user_id)
        image_generation_service_unit._job_store.create.assert_awaited_once_with(
            "job-123", owner_id=user_id
        )

    async def test_spent_quota_creates_no_job(
        self, image_generation_service_unit: ImageGenerationService
    ) -> None:
        image_generation_service_unit._quota_service.consume = AsyncMock(
            side_effect=ImageGenerationLimitExceededError(retry_after=60, limit=3)
        )
        image_generation_service_unit._job_store.create = AsyncMock()

        with pytest.raises(ImageGenerationLimitExceededError):
            await image_generation_service_unit.submit_job(job_id="job-9", user_id=uuid4())
        image_generation_service_unit._job_store.create.assert_not_awaited()

    async def test_run_job_sets_running_then_completed(
        self, image_generation_service_unit: ImageGenerationService
    ) -> None:
        image_generation_service_unit._openrouter_client.generate = AsyncMock(
            return_value=("data:image/png;base64,aGVsbG8=", "openai/gpt-5-image-mini")
        )
        image_generation_service_unit._storage_service.save = AsyncMock(
            return_value=StoredImage("/media/generated-designs/out.png", _asset())
        )
        image_generation_service_unit._job_store.set_state = AsyncMock()

        await image_generation_service_unit.run_job("job-123", "Tiger", "Neon")

        calls = image_generation_service_unit._job_store.set_state.call_args_list
        assert calls[0].args == ("job-123", "running")
        assert calls[1].args[1] == "completed"
        assert calls[1].args[2]["image_url"] == "/media/generated-designs/out.png"
        assert calls[1].args[2]["design_asset"]["key"] == _asset().key

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
        stored = StoredImage("/media/generated-designs/test.png", _asset())
        image_generation_service_unit._storage_service.save = AsyncMock(return_value=stored)
        result = await image_generation_service_unit.save_image("data:image/png;base64,aGVsbG8=")
        assert result == stored


# ── Background removal in the job pipeline ─────────────────────────────────────

class TestBackgroundRemovalInPipeline:
    """The remover sits between the provider and storage, only when requested."""

    @staticmethod
    def _wire(service: ImageGenerationService) -> None:
        service._openrouter_client.generate = AsyncMock(
            return_value=("data:image/png;base64,UFJPVklERVI=", "google/model")
        )
        service._background_remover.remove = AsyncMock(
            return_value="data:image/png;base64,Q1VUT1VU"
        )
        service._storage_service.save = AsyncMock(
            return_value=StoredImage("/media/generated-designs/out.png", _asset())
        )
        service._job_store.set_state = AsyncMock()

    async def test_cutout_is_what_gets_stored(
        self, image_generation_service_unit: ImageGenerationService
    ) -> None:
        self._wire(image_generation_service_unit)

        await image_generation_service_unit.run_job("job-1", "Tiger", "Neon", remove_background=True)

        image_generation_service_unit._background_remover.remove.assert_awaited_once_with(
            "data:image/png;base64,UFJPVklERVI="
        )
        image_generation_service_unit._storage_service.save.assert_awaited_once_with(
            "data:image/png;base64,Q1VUT1VU"
        )
        assert image_generation_service_unit._job_store.set_state.call_args_list[-1].args[1] == "completed"

    async def test_remover_is_skipped_when_not_requested(
        self, image_generation_service_unit: ImageGenerationService
    ) -> None:
        self._wire(image_generation_service_unit)

        await image_generation_service_unit.run_job("job-2", "Tiger", "Neon", remove_background=False)

        image_generation_service_unit._background_remover.remove.assert_not_awaited()
        image_generation_service_unit._storage_service.save.assert_awaited_once_with(
            "data:image/png;base64,UFJPVklERVI="
        )

    async def test_failed_cutout_fails_the_job_and_stores_nothing(
        self, image_generation_service_unit: ImageGenerationService
    ) -> None:
        self._wire(image_generation_service_unit)
        image_generation_service_unit._background_remover.remove = AsyncMock(
            side_effect=ImageBackgroundRemovalError("Background removal left almost nothing")
        )

        await image_generation_service_unit.run_job("job-3", "Tiger", "Neon", remove_background=True)

        image_generation_service_unit._storage_service.save.assert_not_awaited()
        last = image_generation_service_unit._job_store.set_state.call_args_list[-1]
        assert last.args[1] == "failed"
        assert "left almost nothing" in last.args[2]["error"]


# ── Quota refund on failed generation ──────────────────────────────────────────

class TestQuotaRefund:
    async def test_refund_decrements_the_callers_key_atomically(
        self, quota_service: GenerationQuotaService, mock_redis: MagicMock
    ) -> None:
        user_id = uuid4()
        mock_redis.eval = AsyncMock(return_value=2)

        await quota_service.refund(user_id)

        script, key_count, key = mock_redis.eval.call_args.args
        assert key_count == 1
        assert key == f"product-service:image-generation:user:{user_id}"
        assert "DECR" in script and "used > 0" in script

    async def test_job_store_reports_owner(
        self, job_store: ImageJobStore, mock_redis: MagicMock
    ) -> None:
        owner_id = uuid4()
        mock_redis.get = AsyncMock(return_value=str(owner_id).encode())
        assert await job_store.get_owner("job-1") == owner_id

    async def test_job_store_owner_is_none_after_expiry(
        self, job_store: ImageJobStore, mock_redis: MagicMock
    ) -> None:
        mock_redis.get = AsyncMock(return_value=None)
        assert await job_store.get_owner("job-1") is None

    async def test_failed_job_refunds_its_owner(
        self, image_generation_service_unit: ImageGenerationService
    ) -> None:
        owner_id = uuid4()
        service = image_generation_service_unit
        service._openrouter_client.generate = AsyncMock(side_effect=ImageGenerationProviderError("down"))
        service._job_store.set_state = AsyncMock()
        service._job_store.get_owner = AsyncMock(return_value=owner_id)
        service._quota_service.refund = AsyncMock()

        await service.run_job("job-9", "Tiger", "Neon")

        service._quota_service.refund.assert_awaited_once_with(owner_id)

    async def test_completed_job_is_not_refunded(
        self, image_generation_service_unit: ImageGenerationService
    ) -> None:
        service = image_generation_service_unit
        service._openrouter_client.generate = AsyncMock(return_value=("data:image/png;base64,QQ==", "m"))
        service._storage_service.save = AsyncMock(return_value=StoredImage("/media/x.png", _asset()))
        service._job_store.set_state = AsyncMock()
        service._quota_service.refund = AsyncMock()

        await service.run_job("job-10", "Tiger", "Neon")

        service._quota_service.refund.assert_not_awaited()

    async def test_refund_error_does_not_mask_the_job_failure(
        self, image_generation_service_unit: ImageGenerationService
    ) -> None:
        service = image_generation_service_unit
        service._openrouter_client.generate = AsyncMock(side_effect=ImageGenerationProviderError("down"))
        service._job_store.set_state = AsyncMock()
        service._job_store.get_owner = AsyncMock(return_value=uuid4())
        service._quota_service.refund = AsyncMock(side_effect=ConnectionError("redis gone"))

        await service.run_job("job-11", "Tiger", "Neon")   # must not raise

        assert service._job_store.set_state.call_args_list[-1].args[1] == "failed"

    async def test_synchronous_generation_refunds_on_failure(
        self, image_generation_service_unit: ImageGenerationService
    ) -> None:
        user_id = uuid4()
        service = image_generation_service_unit
        service._quota_service.consume = AsyncMock(return_value=5)
        service._quota_service.refund = AsyncMock()
        service._openrouter_client.generate = AsyncMock(side_effect=ImageGenerationProviderError("down"))

        with pytest.raises(ImageGenerationProviderError):
            await service.generate_image("Tiger", "Neon", user_id=user_id)
        service._quota_service.refund.assert_awaited_once_with(user_id)
