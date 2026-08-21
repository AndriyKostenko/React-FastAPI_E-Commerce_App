from logging import Logger
from abc import ABC, abstractmethod
from typing import Any, override
from uuid import UUID

from pydantic import BaseModel

from shared.settings import Settings
from schemas.image_generation_schema import GenerateImageResponse
from exceptions.image_generation_exceptions import ImageGenerationProviderError
from service_layer.image_generation_quota import GenerationQuotaService
from service_layer.image_job_store import ImageJobStore
from service_layer.openrouter_client import OpenRouterClient
from service_layer.image_storage_service import ImageStorageService, StoredImage


class ImageGenerationInterface(ABC):
    @abstractmethod
    async def generate_image(self,
					        prompt: str,
					        style: str,
					        is_guest_user: bool,
					        guest_id: UUID | None = None,
					        user_id: UUID | None = None,
                            remove_background: bool = False) -> BaseModel:
        """Generate an image synchronously and return the result."""
        ...

    @abstractmethod
    async def save_image(self, b64_image: str) -> StoredImage:
        """Validate and persist generated artwork."""
        ...

    @abstractmethod
    async def submit_job(self,
        				job_id: str,
            			prompt: str,
				        style: str,
				        is_guest_user: bool,
				        guest_id: UUID | None = None,
				        user_id: UUID | None = None) -> int | None:
        """Consume quota and persist a pending job in Redis."""
        ...

    @abstractmethod
    async def run_job(self, job_id: str, prompt: str, style: str, remove_background: bool = False) -> None:
        """Execute generation in the background and update job state in Redis."""
        ...

    @abstractmethod
    async def get_job(self, job_id: str) -> dict:
        """Return job state from Redis or raise ImageGenerationJobNotFoundError."""
        ...


class ImageGenerationService(ImageGenerationInterface):
    """
    Thin orchestrator that coordinates quota enforcement, job persistence,
    HTTP generation, and image storage via dedicated collaborators.

    Each collaborator owns a single responsibility:
      - GenerationQuotaService  → Redis-based rate limiting
      - ImageJobStore           → job lifecycle in Redis
      - OpenRouterClient        → HTTP calls to the image provider
      - ImageStorageService     → print validation + durable persistence
    """

    def __init__(self,
		        quota_service: GenerationQuotaService,
		        job_store: ImageJobStore,
		        openrouter_client: OpenRouterClient,
		        storage_service: ImageStorageService,
		        settings: Settings,
		        logger: Logger) -> None:
        self.settings: Settings = settings
        self._logger: Logger = logger
        self._quota_service: GenerationQuotaService = quota_service
        self._job_store: ImageJobStore = job_store
        self._openrouter_client: OpenRouterClient = openrouter_client
        self._storage_service: ImageStorageService = storage_service

    async def _consume_quota(self,
					        is_guest_user: bool,
					        guest_id: UUID | None,
					        user_id: UUID | None) -> int:
        if is_guest_user:
            if not guest_id:
                raise ImageGenerationProviderError("Guest id is required for guest generation")
            return await self._quota_service.consume(guest_id, is_guest=True)
        else:
            if not user_id:
                raise ImageGenerationProviderError(
                    "User id is required for registered user generation"
                )
            return await self._quota_service.consume(user_id, is_guest=False)

    @override
    async def save_image(self, b64_image: str) -> StoredImage:
        return await self._storage_service.save(b64_image)

    @override
    async def generate_image(self,
					        prompt: str,
					        style: str,
					        is_guest_user: bool,
					        guest_id: UUID | None = None,
					        user_id: UUID | None = None,
                            remove_background: bool = False) -> GenerateImageResponse:
        remaining_generations = await self._consume_quota(is_guest_user, guest_id, user_id)
        image_payload, model = await self._openrouter_client.generate(prompt, style, remove_background)
        stored_image = await self._storage_service.save(image_payload)
        self._logger.debug("Image generated and saved: %s", stored_image.asset.key)

        guest_limit = (
            self.settings.PRODUCT_IMAGE_GUEST_GENERATION_LIMIT
            if is_guest_user
            else self.settings.PRODUCT_IMAGE_REGISTERED_GENERATION_LIMIT
        )
        return GenerateImageResponse(
            image_url=stored_image.image_url,
            design_asset=stored_image.asset,
            model=model,
            remaining_generations=remaining_generations,
            guest_limit=guest_limit,
        )

    # ── background-job pattern ──────────────────────────────────────────────

    @override
    async def submit_job(self,
				        job_id: str,
				        prompt: str,
				        style: str,
				        is_guest_user: bool,
				        guest_id: UUID | None = None,
				        user_id: UUID | None = None) -> int | None:
        remaining_generations = await self._consume_quota(is_guest_user, guest_id, user_id)
        await self._job_store.create(job_id)
        return remaining_generations

    @override
    async def run_job(self, job_id: str, prompt: str, style: str, remove_background: bool = False) -> None:
        await self._job_store.set_state(job_id, "running")
        try:
            image_payload, model = await self._openrouter_client.generate(prompt, style, remove_background)
            stored_image = await self._storage_service.save(image_payload)
            await self._job_store.set_state(
                job_id,
                "completed",
                {
                    "image_url": stored_image.image_url,
                    "design_asset": stored_image.asset.model_dump(mode="json"),
                    "model": model,
                },
            )
            self._logger.debug("Job %s completed: %s", job_id, stored_image.asset.key)
        except Exception as exc:
            self._logger.error(f"Job {job_id} failed: {exc}")
            error_message = (
                str(exc)
                if isinstance(exc, ImageGenerationProviderError)
                else "Image generation failed"
            )
            await self._job_store.set_state(
                job_id, "failed", {"error": error_message}
            )

    @override
    async def get_job(self, job_id: str) -> dict[str, Any]:
        return await self._job_store.get(job_id)
