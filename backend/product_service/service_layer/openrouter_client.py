import json
from asyncio import TimeoutError
from logging import Logger
from typing import Any

from aiohttp import ClientError, ClientSession

from shared.settings import Settings
from exceptions.image_generation_exceptions import (
    ImageGenerationConfigurationError,
    ImageGenerationProviderError,
)


class OpenRouterClient:
    """
    Thin HTTP adapter for the OpenRouter chat-completions image endpoint.

    Accepts a shared aiohttp.ClientSession so connection pooling and
    Keep-Alive are managed at the application boundary (lifespan), not
    per-request.
    """

    def __init__(self, session: ClientSession, settings: Settings, logger: Logger) -> None:
        self._session = session
        self._settings = settings
        self._logger = logger
        self._model: str = settings.OPENROUTER_IMAGE_MODEL

    # ── configuration ──────────────────────────────────────────────────────

    def validate_configuration(self) -> None:
        if not self._settings.OPENROUTER_API_KEY:
            raise ImageGenerationConfigurationError(
                "OPENROUTER_API_KEY is missing in service configuration"
            )

    # ── request builders ───────────────────────────────────────────────────

    def _build_prompt(self, prompt: str, style: str, remove_background: bool = False) -> str:
        parts = [f"{prompt.strip()}\n\nStyle reference: {style.strip()}"]
        if remove_background:
            parts.append("Remove the background completely, leaving only the subject.")
        return "\n".join(parts) + "\n"

    def _build_payload(
        self, prompt: str, style: str, remove_background: bool = False
    ) -> dict[str, Any]:
        model = self._model
        is_google = model.startswith("google/")

        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": self._build_prompt(prompt, style, remove_background),
                }
            ],
            "stream": False,
            "modalities": ["image", "text"] if is_google else ["image"],
        }

        image_config: dict[str, Any] = {}
        image_size = self._settings.OPENROUTER_IMAGE_SIZE.strip()
        aspect_ratio = self._settings.OPENROUTER_IMAGE_ASPECT_RATIO.strip()

        if aspect_ratio:
            image_config["aspect_ratio"] = aspect_ratio

        if image_size:
            # Map pixel dimensions (e.g. "512x512") to Gemini quality tags ("1K")
            image_config["image_size"] = "1K" if (is_google and "x" in image_size) else image_size
        elif is_google:
            image_config["image_size"] = "0.5K"

        if not is_google:
            image_config.update(
                {
                    "num_inference_steps": 4,
                    "guidance_scale": 1.0,
                    "response_format": "b64_json",
                }
            )

        if image_config:
            payload["image_config"] = image_config

        return payload

    def _extract_image_payload(self, body: dict[str, Any]) -> str:
        try:
            payload = body["choices"][0]["message"]["images"][0]["image_url"]["url"]
            if not isinstance(payload, str) or not payload.strip():
                raise ValueError
            return payload
        except (KeyError, IndexError, TypeError, ValueError):
            raise ImageGenerationProviderError("No image returned from provider")

    # ── core HTTP call ──────────────────────────────────────────────────────

    async def generate(
        self, prompt: str, style: str, remove_background: bool = False
    ) -> tuple[str, str]:
        """
        Call the OpenRouter completions endpoint.

        Returns:
            Tuple of (image_payload, model_name).
        Raises:
            ImageGenerationConfigurationError: API key is not configured.
            ImageGenerationProviderError: HTTP error or unexpected response shape.
        """
        self.validate_configuration()
        payload = self._build_payload(prompt, style, remove_background)
        headers = {
            "Authorization": f"Bearer {self._settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._settings.FRONTEND_URL,
            "X-OpenRouter-Title": self._settings.WEBSITE_NAME,
        }
        endpoint = f"{self._settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"

        try:
            async with self._session.post(endpoint, headers=headers, json=payload) as response:
                raw = await response.text()
                try:
                    body: dict[str, Any] = json.loads(raw) if raw.strip() else {}
                except json.JSONDecodeError:
                    body = {"raw": raw}

                if response.status >= 400:
                    self._logger.error(
                        f"OpenRouter generation failed (HTTP {response.status}): {body or raw!r}"
                    )
                    raise ImageGenerationProviderError(
                        f"OpenRouter request failed with status {response.status}"
                    )
        except ImageGenerationProviderError:
            raise
        except (ClientError, TimeoutError) as error:
            self._logger.error(f"OpenRouter connection failure: {error}")
            raise ImageGenerationProviderError(
                "Failed to connect to image generation provider"
            )

        return self._extract_image_payload(body), self._model
