from logging import Logger
from abc import ABC, abstractmethod
from typing import Any, override
from uuid import UUID

from pydantic import BaseModel

from shared.settings import Settings
from schemas.image_generation_schema import GenerateImageResponse
from exceptions.image_generation_exceptions import (
    ImageBackgroundRemovalError,
    ImageGenerationProviderError,
)
from service_layer.background_removal_service import BackgroundRemover
from service_layer.image_generation_quota import GenerationQuotaService
from service_layer.image_job_store import ImageJobStore
from service_layer.openrouter_client import OpenRouterClient
from service_layer.image_storage_service import ImageStorageService, StoredImage


class ImageGenerationInterface(ABC):
    @abstractmethod
    async def generate_image(self,
                            prompt: str,
                            style: str,
                            user_id: UUID,
                            remove_background: bool = False) -> BaseModel:
        """Generate an image synchronously and return the result."""
        ...

    @abstractmethod
    async def save_image(self, b64_image: str) -> StoredImage:
        """Validate and persist generated artwork."""
        ...

    @abstractmethod
    async def submit_job(self, job_id: str, user_id: UUID) -> int:
        """Consume the user's quota and persist a pending job in Redis."""
        ...

    @abstractmethod
    async def run_job(self, job_id: str, prompt: str, style: str, remove_background: bool = False) -> None:
        """Execute generation in the background and update job state in Redis."""
        ...

    @abstractmethod
    async def get_job(self, job_id: str, user_id: UUID) -> dict:
        """Return the user's job state or raise ImageGenerationJobNotFoundError."""
        ...


class ImageGenerationService(ImageGenerationInterface):
    """
    Thin orchestrator that coordinates quota enforcement, job persistence,
    HTTP generation, and image storage via dedicated collaborators.

    Each collaborator owns a single responsibility:
      - GenerationQuotaService  → per-user Redis quota
      - ImageJobStore           → job lifecycle in Redis
      - OpenRouterClient        → HTTP calls to the image provider
      - BackgroundRemover       → transparent cutout when requested
      - ImageStorageService     → print validation + durable persistence
    """

    def __init__(self,
                 quota_service: GenerationQuotaService,
                 job_store: ImageJobStore,
                 openrouter_client: OpenRouterClient,
                 storage_service: ImageStorageService,
                 background_remover: BackgroundRemover,
                 settings: Settings,
                 logger: Logger) -> None:
        self.settings: Settings = settings
        self._logger: Logger = logger
        self._quota_service: GenerationQuotaService = quota_service
        self._job_store: ImageJobStore = job_store
        self._openrouter_client: OpenRouterClient = openrouter_client
        self._storage_service: ImageStorageService = storage_service
        self._background_remover: BackgroundRemover = background_remover

    async def _produce_artwork(
        self, prompt: str, style: str, remove_background: bool
    ) -> tuple[str, str]:
        """Generate the image and, when asked, cut it out before it is stored."""
        image_payload, model = await self._openrouter_client.generate(prompt, style, remove_background)
        if remove_background:
            # Image models ignore transparency requests and paint a backdrop,
            # which would print as a solid rectangle on the garment.
            image_payload = await self._background_remover.remove(image_payload)
        return image_payload, model

    @override
    async def save_image(self, b64_image: str) -> StoredImage:
        return await self._storage_service.save(b64_image)

    @override
    async def generate_image(self,
                            prompt: str,
                            style: str,
                            user_id: UUID,
                            remove_background: bool = False) -> GenerateImageResponse:
        remaining_generations = await self._quota_service.consume(user_id)
        try:
            image_payload, model = await self._produce_artwork(prompt, style, remove_background)
            stored_image = await self._storage_service.save(image_payload)
        except Exception:
            await self._refund_quietly(user_id)
            raise
        self._logger.debug("Image generated and saved: %s", stored_image.asset.key)
        return GenerateImageResponse(
            image_url=stored_image.image_url,
            design_asset=stored_image.asset,
            model=model,
            remaining_generations=remaining_generations,
            generation_limit=self.settings.PRODUCT_IMAGE_GENERATION_LIMIT,
        )

    # ── background-job pattern ──────────────────────────────────────────────

    @override
    async def submit_job(self, job_id: str, user_id: UUID) -> int:
        remaining_generations = await self._quota_service.consume(user_id)
        await self._job_store.create(job_id, owner_id=user_id)
        return remaining_generations

    @override
    async def run_job(self, job_id: str, prompt: str, style: str, remove_background: bool = False) -> None:
        await self._job_store.set_state(job_id, "running")
        try:
            image_payload, model = await self._produce_artwork(prompt, style, remove_background)
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
            # Our own errors carry a safe, user-facing message; anything else
            # is an internal failure whose details stay in the log.
            error_message = (
                str(exc)
                if isinstance(exc, (ImageGenerationProviderError, ImageBackgroundRemovalError))
                else "Image generation failed"
            )
            await self._job_store.set_state(
                job_id, "failed", {"error": error_message}
            )
            # The quota was spent at submit time; a job that produced no
            # artwork gives it back.
            owner_id = await self._job_store.get_owner(job_id)
            if owner_id is not None:
                await self._refund_quietly(owner_id)

    async def _refund_quietly(self, user_id: UUID) -> None:
        """Refund a generation; a Redis hiccup must not mask the original failure."""
        try:
            await self._quota_service.refund(user_id)
        except Exception as refund_error:
            self._logger.error("Could not refund generation quota for %s: %s", user_id, refund_error)

    @override
    async def get_job(self, job_id: str, user_id: UUID) -> dict[str, Any]:
        return await self._job_store.get(job_id, owner_id=user_id)
