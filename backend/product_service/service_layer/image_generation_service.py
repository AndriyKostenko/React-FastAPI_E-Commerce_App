import base64
from logging import Logger
import os
from pathlib import Path
from uuid import uuid4

import aiofiles
import aiohttp

from shared.settings import Settings
from shared.managers.cache_manager import CacheManager
from shared.schemas.image_generation_schema import GenerateImageResponse
from exceptions.image_generation_exceptions import (
    ImageGenerationConfigurationError,
    ImageGenerationLimitExceededError,
    ImageGenerationProviderError,
)


class ImageGenerationService:
    """

    """
    def __init__(self, settings: Settings, cache_manager: CacheManager, logger: Logger):
        self.settings = settings
        self.cache_manager = cache_manager
        self.logger = logger

    async def _consume_guest_quota(self, guest_id: str) -> int:
        key = f"{self.cache_manager.service_prefix}:image-generation:guest:{guest_id}"
        limit = self.settings.PRODUCT_IMAGE_GUEST_GENERATION_LIMIT
        window_seconds = self.settings.PRODUCT_IMAGE_GUEST_GENERATION_WINDOW_HOURS * 3600

        current_count = await self.cache_manager.redis.incr(key)
        if current_count == 1:
            await self.cache_manager.redis.expire(key, window_seconds)

        ttl = await self.cache_manager.redis.ttl(key)
        retry_after = max(ttl, 1)

        if current_count > limit:
            raise ImageGenerationLimitExceededError(retry_after=retry_after, limit=limit)

        return max(limit - current_count, 0)

    async def _save_generated_image(self, b64_image: str) -> str:
        media_root = Path(os.environ.get("MEDIA_ROOT", "/media"))
        generated_dir = media_root / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{uuid4().hex}.png"
        output_file = generated_dir / filename
        image_bytes = base64.b64decode(b64_image)

        async with aiofiles.open(output_file, "wb") as file:
            await file.write(image_bytes)

        return f"/media/generated/{filename}"

    def _build_prompt(self, prompt: str, style: str) -> str:
        return f"{prompt.strip()}\n\nStyle reference: {style.strip()}"

    def _validate_configuration(self) -> None:
        if not self.settings.OPENROUTER_API_KEY:
            raise ImageGenerationConfigurationError(
                "OPENROUTER_API_KEY is missing in service configuration"
            )

    async def generate_image(
        self,
        prompt: str,
        style: str,
        is_guest_user: bool,
        guest_id: str | None = None,
    ) -> GenerateImageResponse:
        self._validate_configuration()

        remaining_generations = None
        if is_guest_user:
            if not guest_id:
                raise ImageGenerationProviderError("Guest id is required for guest generation")
            remaining_generations = await self._consume_guest_quota(guest_id)

        payload = {
            "model": self.settings.OPENROUTER_IMAGE_MODEL,
            "prompt": self._build_prompt(prompt, style),
            "n": 1,
            "size": "1024x1024",
        }
        headers = {
            "Authorization": f"Bearer {self.settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.FRONTEND_URL,
            "X-Title": "react-fastapi-ecommerce",
        }
        endpoint = f"{self.settings.OPENROUTER_BASE_URL.rstrip('/')}/images/generations"

        timeout = aiohttp.ClientTimeout(total=90)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(endpoint, headers=headers, json=payload) as response:
                    body = await response.json(content_type=None)
                    if response.status >= 400:
                        self.logger.error(f"OpenRouter generation failed: {body}")
                        raise ImageGenerationProviderError(
                            f"OpenRouter request failed with status {response.status}"
                        )
        except ImageGenerationProviderError:
            raise
        except aiohttp.ClientError as error:
            self.logger.error(f"OpenRouter connection failure: {error}")
            raise ImageGenerationProviderError("Failed to connect to image generation provider")

        data = body.get("data", [])
        if not data:
            raise ImageGenerationProviderError("No image returned from provider")

        first_result = data[0]
        image_url = first_result.get("url")
        if not image_url and first_result.get("b64_json"):
            image_url = await self._save_generated_image(first_result["b64_json"])

        if not image_url:
            raise ImageGenerationProviderError("Unsupported provider response format")

        return GenerateImageResponse(
            image_url=image_url,
            model=self.settings.OPENROUTER_IMAGE_MODEL,
            remaining_generations=remaining_generations,
            guest_limit=self.settings.PRODUCT_IMAGE_GUEST_GENERATION_LIMIT
            if is_guest_user
            else None,
        )
