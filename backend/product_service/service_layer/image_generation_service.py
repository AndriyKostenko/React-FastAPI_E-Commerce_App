from collections.abc import Awaitable
from logging import Logger
from abc import ABC, abstractmethod
from typing import Any, override
from uuid import UUID

from pydantic import BaseModel

from settings import Settings
from schemas.image_generation_schema import GenerateImageResponse
from exceptions.image_generation_exceptions import (
    DesignCheckUnavailableError,
    DesignRefusedError,
    ImageBackgroundRemovalError,
    ImageGenerationProviderError,
)
from service_layer.background_removal_service import BackgroundRemover
from service_layer.design_moderation import (
    DesignModerationUnavailableError,
    DesignModerator,
    DesignRefusal,
    DesignRefusalLog,
)
from service_layer.generated_design_log import GeneratedDesignLog
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
      - DesignModerator         → checks the request, then the image
      - DesignRefusalLog        → keeps each refused design for the admins
      - GeneratedDesignLog      → notes each stored design and its owner (retention)
      - ImageStorageService     → print validation + durable persistence
    """

    # Failures whose message is written for the customer; anything else is
    # an internal failure whose details stay in the log.
    _CUSTOMER_FACING_ERRORS = (
        ImageGenerationProviderError,
        ImageBackgroundRemovalError,
        DesignRefusedError,
        DesignCheckUnavailableError,
    )

    def __init__(self,
                 quota_service: GenerationQuotaService,
                 job_store: ImageJobStore,
                 openrouter_client: OpenRouterClient,
                 storage_service: ImageStorageService,
                 background_remover: BackgroundRemover,
                 moderator: DesignModerator,
                 refusal_log: DesignRefusalLog,
                 design_log: GeneratedDesignLog,
                 settings: Settings,
                 logger: Logger) -> None:
        self.settings: Settings = settings
        self._logger: Logger = logger
        self._quota_service: GenerationQuotaService = quota_service
        self._job_store: ImageJobStore = job_store
        self._openrouter_client: OpenRouterClient = openrouter_client
        self._storage_service: ImageStorageService = storage_service
        self._background_remover: BackgroundRemover = background_remover
        self._moderator: DesignModerator = moderator
        self._refusal_log: DesignRefusalLog = refusal_log
        self._design_log: GeneratedDesignLog = design_log

    async def _produce_artwork(
        self, prompt: str, style: str, remove_background: bool, user_id: UUID | None
    ) -> tuple[str, str]:
        """
        Check the request, generate the image (cut out when asked), then check
        the image. Only a design both checks passed goes on to be stored and
        signed, and only a signed design can be ordered.
        """
        # The request first: an obviously refused one costs no image.
        await self._enforce(self._moderator.check_prompt(prompt, style), user_id, prompt, style)
        image_payload, model = await self._openrouter_client.generate(prompt, style, remove_background)
        if remove_background:
            # Image models ignore transparency requests and paint a backdrop,
            # which would print as a solid rectangle on the garment.
            image_payload = await self._background_remover.remove(image_payload)
        # Checked as it will be printed: after the cutout.
        await self._enforce(self._moderator.check_image(image_payload, prompt), user_id, prompt, style)
        return image_payload, model

    async def _enforce(
        self, check: Awaitable[DesignRefusal | None], user_id: UUID | None, prompt: str, style: str
    ) -> None:
        """Let the design through, or stop it: refused, or unchecked (fail closed)."""
        try:
            refusal = await check
        except DesignModerationUnavailableError as error:
            self._logger.warning("Design check unavailable, design not produced: %s", error)
            raise DesignCheckUnavailableError() from error
        if refusal is None:
            return
        self._logger.info(
            "Design refused at the %s check (%s) for user %s", refusal.stage, refusal.category, user_id
        )
        try:
            await self._refusal_log.record(user_id, prompt, style, refusal)
        except Exception as error:
            # The refusal stands even when it cannot be kept.
            self._logger.error("Could not record a design refusal: %s", error)
        raise DesignRefusedError(refusal.category.customer_message)

    async def _store(self, image_payload: str, user_id: UUID | None) -> StoredImage:
        """Store and sign the design, and note it for the retention job."""
        stored_image = await self._storage_service.save(image_payload)
        try:
            await self._design_log.record(stored_image.asset.key, user_id)
        except Exception as error:
            # The customer still gets the design; only its automatic deletion is lost.
            self._logger.error(
                "Design %s stored but not recorded, so it will not be deleted automatically: %s",
                stored_image.asset.key, error,
            )
        return stored_image

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
            image_payload, model = await self._produce_artwork(prompt, style, remove_background, user_id)
            stored_image = await self._store(image_payload, user_id)
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
        owner_id = await self._job_store.get_owner(job_id)
        try:
            image_payload, model = await self._produce_artwork(prompt, style, remove_background, owner_id)
            stored_image = await self._store(image_payload, owner_id)
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
            # A refusal is the check doing its job (_enforce logged it), not a failure.
            if not isinstance(exc, DesignRefusedError):
                self._logger.error(f"Job {job_id} failed: {exc}")
            # The detail alone: str() of an HTTP exception starts with its
            # status code, which is not for the customer.
            error_message = (
                str(exc.detail)
                if isinstance(exc, self._CUSTOMER_FACING_ERRORS)
                else "Image generation failed"
            )
            await self._job_store.set_state(
                job_id, "failed", {"error": error_message}
            )
            # The quota was spent at submit time; a job that produced no
            # artwork (refused designs included) gives it back.
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
