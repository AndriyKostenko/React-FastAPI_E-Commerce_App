"""One question to an OpenRouter chat model whose answer must fit a JSON schema."""

import json
from asyncio import TimeoutError
from logging import Logger

from aiohttp import ClientError, ClientSession, ClientTimeout
from pydantic import BaseModel, JsonValue, ValidationError
from settings import Settings

type ChatMessage = dict[str, JsonValue]


class StructuredAnswerUnavailableError(Exception):
    """No answer this time: no key, provider down or slow, or an answer that does not fit."""


class OpenRouterStructuredChat:
    """
    The transport shared by the model checks (supplier photo review, design
    moderation): the request is constrained to a JSON schema, and the answer
    is validated against a pydantic model. Anything that does not fit is "no
    answer", never a guess, so callers can fail closed.
    """

    def __init__(
        self,
        session: ClientSession,
        settings: Settings,
        logger: Logger,
        *,
        model: str,
        timeout_seconds: float,
        purpose: str,
    ) -> None:
        self._session = session
        self._settings = settings
        self._logger = logger
        self._model = model
        self._timeout = ClientTimeout(total=timeout_seconds)
        # Names the check in log lines ("review", "moderation").
        self._purpose = purpose

    @property
    def model(self) -> str:
        return self._model

    def require_key(self) -> None:
        if not self._settings.OPENROUTER_API_KEY:
            raise StructuredAnswerUnavailableError(
                "OPENROUTER_API_KEY is not configured"
            )

    def payload(
        self,
        messages: list[ChatMessage],
        schema_name: str,
        schema: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        return {
            "model": self._model,
            "temperature": 0,
            "stream": False,
            "messages": list(messages),
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
        }

    async def ask[AnswerT: BaseModel](
        self,
        messages: list[ChatMessage],
        schema_name: str,
        schema: dict[str, JsonValue],
        answer_type: type[AnswerT],
    ) -> AnswerT:
        self.require_key()
        body = await self.post(self.payload(messages, schema_name, schema))
        return self.parse(body, answer_type)

    async def post(self, payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
        headers = {
            "Authorization": f"Bearer {self._settings.OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._settings.FRONTEND_URL,
            "X-OpenRouter-Title": self._settings.WEBSITE_NAME,
        }
        endpoint = f"{self._settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
        try:
            async with self._session.post(
                endpoint, headers=headers, json=payload, timeout=self._timeout
            ) as response:
                raw = await response.text()
                if response.status >= 400:
                    # The body is the provider's error; the image is not in it.
                    self._logger.warning(
                        "OpenRouter %s failed (HTTP %s): %s",
                        self._purpose,
                        response.status,
                        raw[:500],
                    )
                    raise StructuredAnswerUnavailableError(
                        f"OpenRouter answered HTTP {response.status}"
                    )
        except (ClientError, TimeoutError) as error:
            raise StructuredAnswerUnavailableError(
                f"OpenRouter could not be reached: {error!r}"
            ) from error
        try:
            body = json.loads(raw)
        except json.JSONDecodeError as error:
            raise StructuredAnswerUnavailableError(
                "OpenRouter answered with something other than JSON"
            ) from error
        if not isinstance(body, dict):
            raise StructuredAnswerUnavailableError(
                "OpenRouter answered with an unexpected shape"
            )
        return body

    @staticmethod
    def parse[AnswerT: BaseModel](
        body: dict[str, JsonValue], answer_type: type[AnswerT]
    ) -> AnswerT:
        try:
            content = body["choices"][0]["message"]["content"]  # type: ignore[index]
        except (KeyError, IndexError, TypeError) as error:
            raise StructuredAnswerUnavailableError(
                "OpenRouter's answer has no message"
            ) from error
        if not isinstance(content, str):
            raise StructuredAnswerUnavailableError("OpenRouter's message is not text")
        # Some models wrap JSON in a markdown fence even when a schema is given.
        text = (
            content.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        try:
            return answer_type.model_validate_json(text)
        except ValidationError as error:
            raise StructuredAnswerUnavailableError(
                f"the model's answer does not fit the schema: {error.errors()[0]['msg']}"
            ) from error
