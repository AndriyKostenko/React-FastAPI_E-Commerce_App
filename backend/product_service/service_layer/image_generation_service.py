from asyncio import TimeoutError
import base64
import json
import time
from logging import Logger
import os
from pathlib import Path
from typing import Any, override
from uuid import uuid4
from abc import ABC, abstractmethod

import aiofiles
from aiohttp import ClientTimeout, ClientSession, ClientError
from orjson import loads as orjson_loads, dumps as orjson_dumps
from pydantic import BaseModel

from shared.settings import Settings
from shared.managers.cache_manager import CacheManager
from shared.schemas.image_generation_schema import GenerateImageResponse
from exceptions.image_generation_exceptions import (
    ImageGenerationConfigurationError,
    ImageGenerationJobNotFoundError,
    ImageGenerationLimitExceededError,
    ImageGenerationProviderError,
)

class ImageGenerationInterface(ABC):
    @abstractmethod
    async def generate_image(self,  prompt: str, style: str, is_guest_user: bool, guest_id: str | None = None, user_id: str | None = None, remove_background: bool = False) -> BaseModel:
        """Generating an image"""
        ...
    @abstractmethod
    async def save_image(self, b64_image: str) -> str:
        """Saving the generated image"""
        ...
    @abstractmethod
    async def submit_job(self, job_id: str, prompt: str, style: str, is_guest_user: bool, guest_id: str | None = None, user_id: str | None = None) -> int | None:
        """Validate, consume quota, and persist a pending job in Redis."""
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

    # TTL for background-job state keys in Redis.
    _JOB_TTL: int = 3600  # 1 hour

    def __init__(self, settings: Settings, cache_manager: CacheManager, logger: Logger):
        self.settings: Settings = settings
        self.cache_manager: CacheManager = cache_manager
        self.logger: Logger = logger
        self.timeout: ClientTimeout = ClientTimeout(total=45)
        self.GUEST_QUOTA_COOKIE: str = settings.GUEST_QUOTA_COOKIE

    # ---- guest quota ----

    async def _consume_guest_quota(self, guest_id: str) -> int:
        key = f"{self.cache_manager.service_prefix}:image-generation:guest:{guest_id}"
        limit = self.settings.PRODUCT_IMAGE_GUEST_GENERATION_LIMIT
        window_seconds = self.settings.PRODUCT_IMAGE_GUEST_GENERATION_WINDOW_HOURS * 3600

        current_count = await self.cache_manager.redis.incr(key)
        if current_count == 1:
            await self.cache_manager.redis.expire(key, window_seconds)
        else:
            ttl = await self.cache_manager.redis.ttl(key)
            if ttl == -1:
                # Key exists but has no TTL (expire was lost between calls) — restore it.
                await self.cache_manager.redis.expire(key, window_seconds)

        ttl = await self.cache_manager.redis.ttl(key)
        retry_after = max(ttl, 1)

        if current_count > limit:
            raise ImageGenerationLimitExceededError(retry_after=retry_after, limit=limit)

        return max(limit - current_count, 0)

    async def _consume_registered_quota(self, user_id: str) -> int:
        key = f"{self.cache_manager.service_prefix}:image-generation:registered:{user_id}"
        limit = self.settings.PRODUCT_IMAGE_REGISTERED_GENERATION_LIMIT
        window_seconds = self.settings.PRODUCT_IMAGE_GUEST_GENERATION_WINDOW_HOURS * 3600

        current_count = await self.cache_manager.redis.incr(key)
        if current_count == 1:
            await self.cache_manager.redis.expire(key, window_seconds)
        else:
            ttl = await self.cache_manager.redis.ttl(key)
            if ttl == -1:
                # Key exists but has no TTL (expire was lost between calls) — restore it.
                await self.cache_manager.redis.expire(key, window_seconds)

        ttl = await self.cache_manager.redis.ttl(key)
        retry_after = max(ttl, 1)

        if current_count > limit:
            raise ImageGenerationLimitExceededError(retry_after=retry_after, limit=limit)

        return max(limit - current_count, 0)

    # ---- image persistence ----

    @override
    async def save_image(self, b64_image: str) -> str:
        try:
            media_root = Path(os.environ.get("MEDIA_ROOT", "/media"))
            generated_dir = media_root / "generated"
            generated_dir.mkdir(parents=True, exist_ok=True)

            filename = f"{uuid4().hex}.png"
            output_file = generated_dir / filename
            image_payload = b64_image.strip()
            if image_payload.startswith("data:"):
                _, separator, image_payload = image_payload.partition(",")
                if not separator or not image_payload:
                    raise ValueError("Invalid image data URL")
            image_bytes = base64.b64decode(image_payload, validate=True)

            async with aiofiles.open(output_file, "wb") as file:
                await file.write(image_bytes)

            return f"/media/generated/{filename}"
        except (ValueError, OSError) as error:
            self.logger.error(f"Failed to save generated image: {error}")
            raise ImageGenerationProviderError("Failed to save generated image to disk")

    # ---- request building ----

    def _build_prompt(self, prompt: str, style: str, remove_background: bool = False) -> str:
        base_prompt = f"{prompt.strip()}\n\nStyle reference: {style.strip()}"
        if not remove_background:
            return base_prompt
        return (
            f"{base_prompt}\n\n"
            "Background instruction: Remove the background completely and return a transparent background."
        )

    def _resolve_image_model(self) -> str:
        configured_model = self.settings.OPENROUTER_IMAGE_MODEL.strip()
        if configured_model in {"", "openai/gpt-5-image-mini"}:
            return "google/gemini-3.1-flash-image-preview"
        return configured_model

    def _build_openrouter_payload(self, model: str, prompt: str, style: str, remove_background: bool = False) -> dict:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": self._build_prompt(prompt, style, remove_background),
                }
            ],
            "stream": False,
        }

        is_google_image_model = model.startswith("google/")
        payload["modalities"] = ["image", "text"] if is_google_image_model else ["image"]

        if not is_google_image_model:
            image_config = {}
            image_size = self.settings.OPENROUTER_IMAGE_SIZE.strip()
            aspect_ratio = self.settings.OPENROUTER_IMAGE_ASPECT_RATIO.strip()
            if image_size:
                image_config["image_size"] = image_size
            if aspect_ratio:
                image_config["aspect_ratio"] = aspect_ratio
            if image_config:
                payload["image_config"] = image_config

        return payload

    def _extract_image_payload(self, body: dict[str, Any]) -> str:
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ImageGenerationProviderError("No image returned from provider")

        first_choice = choices[0]
        message = first_choice.get("message", {}) if isinstance(first_choice, dict) else {}
        images = message.get("images", []) if isinstance(message, dict) else []
        if not isinstance(images, list) or not images:
            raise ImageGenerationProviderError("No image returned from provider")

        first_image = images[0]
        image_url = first_image.get("image_url", {}) if isinstance(first_image, dict) else {}
        payload = image_url.get("url") if isinstance(image_url, dict) else None
        if not isinstance(payload, str) or not payload.strip():
            raise ImageGenerationProviderError("Unsupported provider response format")

        return payload

    def _validate_configuration(self) -> None:
        if not self.settings.OPENROUTER_API_KEY:
            raise ImageGenerationConfigurationError(
                "OPENROUTER_API_KEY is missing in service configuration"
            )

    # ---- core HTTP call ----

    async def _call_openrouter(self, prompt: str, style: str, remove_background: bool = False) -> tuple[str, str]:
        """
        Send a generation request to OpenRouter and return (image_b64_payload, model_name).
        Raises ImageGenerationProviderError on any network or upstream failure.
        """
        model = self._resolve_image_model()
        payload = self._build_openrouter_payload(
            model=model,
            prompt=prompt,
            style=style,
            remove_background=remove_background,
        )
        headers = {
            "Authorization": f"Bearer {self.settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.FRONTEND_URL,
            "X-OpenRouter-Title": "react-fastapi-ecommerce",
        }
        endpoint = f"{self.settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"

        try:
            async with ClientSession(timeout=self.timeout) as session:
                async with session.post(endpoint, headers=headers, json=payload) as response:
                    raw = await response.text()
                    try:
                        body = json.loads(raw) if raw.strip() else {}
                    except json.JSONDecodeError:
                        body = {"raw": raw}
                    if response.status >= 400:
                        self.logger.error(
                            f"OpenRouter generation failed (HTTP {response.status}): {body or raw!r}"
                        )
                        raise ImageGenerationProviderError(
                            f"OpenRouter request failed with status {response.status}"
                        )
        except ImageGenerationProviderError:
            raise
        except (ClientError, TimeoutError) as error:
            self.logger.error(f"OpenRouter connection failure: {error}")
            raise ImageGenerationProviderError("Failed to connect to image generation provider")

        return self._extract_image_payload(body), model

    # ---- synchronous (legacy) generation ----

    @override
    async def generate_image(
        self,
        prompt: str,
        style: str,
        is_guest_user: bool,
        guest_id: str | None = None,
        user_id: str | None = None,
        remove_background: bool = False,
    ) -> GenerateImageResponse:
        self._validate_configuration()

        remaining_generations = None
        guest_limit = None
        
        if is_guest_user:
            if not guest_id:
                raise ImageGenerationProviderError("Guest id is required for guest generation")
            remaining_generations = await self._consume_guest_quota(guest_id)
            guest_limit = self.settings.PRODUCT_IMAGE_GUEST_GENERATION_LIMIT
        else:
            if not user_id:
                raise ImageGenerationProviderError("User id is required for registered user generation")
            remaining_generations = await self._consume_registered_quota(user_id)
            guest_limit = self.settings.PRODUCT_IMAGE_REGISTERED_GENERATION_LIMIT

        image_payload, model = await self._call_openrouter(prompt, style, remove_background)
        image_url = await self.save_image(image_payload)
        self.logger.debug(f"Image is generated and saved: {image_url}")

        return GenerateImageResponse(
            image_url=image_url,
            model=model,
            remaining_generations=remaining_generations,
            guest_limit=guest_limit,
        )

    # ---- background-job pattern ----

    def _job_key(self, job_id: str) -> str:
        return f"{self.cache_manager.service_prefix}:image-job:{job_id}"

    @override
    async def submit_job(
        self,
        job_id: str,
        prompt: str,
        style: str,
        is_guest_user: bool,
        guest_id: str | None = None,
        user_id: str | None = None,
    ) -> int | None:
        """
        Validate the request, consume guest quota (fails-fast on 429), and
        write a ``pending`` job record to Redis.  Returns remaining_generations.

        Note: BackgroundTasks runs within the same worker process — job state
        is lost if the worker restarts before run_job completes.
        """
        self._validate_configuration()

        remaining_generations = None
        if is_guest_user:
            if not guest_id:
                raise ImageGenerationProviderError("Guest id is required for guest generation")
            remaining_generations = await self._consume_guest_quota(guest_id)
        else:
            if not user_id:
                raise ImageGenerationProviderError("User id is required for registered user generation")
            remaining_generations = await self._consume_registered_quota(user_id)

        job_data: dict[str, Any] = {
            "status": "pending",
            "submitted_at": time.time(),
        }
        await self.cache_manager.redis.setex(
            name=self._job_key(job_id),
            time=self._JOB_TTL,
            value=orjson_dumps(job_data),
        )
        return remaining_generations

    @override
    async def run_job(self, job_id: str, prompt: str, style: str, remove_background: bool = False) -> None:
        """
        Execute image generation as a background task and update Redis job state.
        Called by FastAPI BackgroundTasks after the 202 response is sent.
        """
        key = self._job_key(job_id)

        async def _update(updates: dict) -> None:
            raw = await self.cache_manager.redis.get(key)
            data = orjson_loads(raw) if raw else {}
            data.update(updates)
            await self.cache_manager.redis.setex(name=key, time=self._JOB_TTL, value=orjson_dumps(data))

        await _update({"status": "running"})
        try:
            image_payload, model = await self._call_openrouter(prompt, style, remove_background)
            image_url = await self.save_image(image_payload)
            await _update({"status": "completed", "image_url": image_url, "model": model})
            self.logger.debug(f"Job {job_id} completed: {image_url}")
        except Exception as exc:
            self.logger.error(f"Job {job_id} failed: {exc}")
            # Store a sanitised error — never leak raw provider messages to the client.
            await _update({"status": "failed", "error": "Image generation failed"})

    @override
    async def get_job(self, job_id: str) -> dict:
        """
        Return the current job state dict.
        Raises ImageGenerationJobNotFoundError if the key is missing or expired.
        """
        raw = await self.cache_manager.redis.get(self._job_key(job_id))
        if not raw:
            raise ImageGenerationJobNotFoundError()
        return orjson_loads(raw)
