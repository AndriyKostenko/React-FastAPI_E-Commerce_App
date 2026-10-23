"""
OpenRouterDesignModerator without the network: what it sends for each check,
how it reads the model's answer, and that anything it cannot trust counts as
no answer (never as "allowed"). The real requests are the opt-in live test.
"""

import base64
import io
import json
from logging import getLogger

import pytest
from PIL import Image
from pydantic import JsonValue, SecretStr

from resources import settings
from service_layer.design_moderation import (
    DesignModerationUnavailableError,
    ModerationCategory,
    ModerationStage,
)
from service_layer.openrouter_design_moderator import OpenRouterDesignModerator


def _answer(allowed: bool, category: str, reason: str = "One sentence.") -> dict[str, JsonValue]:
    content = json.dumps({"allowed": allowed, "category": category, "reason": reason})
    return {"choices": [{"message": {"content": content}}]}


class _Response:
    def __init__(self, status: int, body: dict[str, JsonValue]) -> None:
        self.status = status
        self._body = body

    async def __aenter__(self) -> "_Response":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def text(self) -> str:
        return json.dumps(self._body)


class _Session:
    """Answers every POST with one canned response, and keeps what was sent."""

    def __init__(self, status: int = 200, body: dict[str, JsonValue] | None = None) -> None:
        self._response = _Response(status, body if body is not None else _answer(True, "none"))
        self.sent: list[dict[str, JsonValue]] = []

    def post(self, endpoint: str, headers: dict[str, str], json: dict[str, JsonValue], timeout: object) -> _Response:
        self.sent.append(json)
        return self._response


def _moderator(session: _Session, key: str | None = "test-key") -> OpenRouterDesignModerator:
    return OpenRouterDesignModerator(
        session=session,  # type: ignore[arg-type]
        settings=settings.model_copy(update={"OPENROUTER_API_KEY": SecretStr(key) if key else None}),
        logger=getLogger("test"),
    )


def _transparent_print_file() -> str:
    """A 3000 px transparent design with one white square: what a cutout looks like."""
    image = Image.new("RGBA", (3000, 3000), (0, 0, 0, 0))
    image.paste((255, 255, 255, 255), (1000, 1000, 2000, 2000))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


class TestTheRequestCheck:
    async def test_sends_the_rules_and_the_request_as_text_to_judge(self) -> None:
        session = _Session()
        assert await _moderator(session).check_prompt("  A tiger in neon  ", "Synthwave") is None

        [payload] = session.sent
        system, user = payload["messages"]
        assert OpenRouterDesignModerator.POLICY in system["content"]
        assert OpenRouterDesignModerator.PROMPT_STAGE in system["content"]
        assert user["content"] == "Description: A tiger in neon\nStyle: Synthwave"
        assert payload["model"] == settings.OPENROUTER_MODERATION_MODEL and payload["temperature"] == 0
        assert payload["response_format"]["json_schema"]["strict"] is True

    async def test_a_refusal_carries_its_rule_and_the_models_reason(self) -> None:
        session = _Session(body=_answer(False, "character", "It asks for Pikachu."))
        refusal = await _moderator(session).check_prompt("Pikachu surfing", "Anime")
        assert refusal is not None
        assert (refusal.stage, refusal.category) == (ModerationStage.PROMPT, ModerationCategory.CHARACTER)
        assert refusal.reason == "It asks for Pikachu."
        assert refusal.model == settings.OPENROUTER_MODERATION_MODEL


class TestTheImageCheck:
    async def test_sends_the_image_inline_scaled_down_on_grey(self) -> None:
        session = _Session(body=_answer(False, "brand"))
        refusal = await _moderator(session).check_image(_transparent_print_file(), "A logo")
        assert refusal is not None and refusal.stage is ModerationStage.IMAGE

        [payload] = session.sent
        system, user = payload["messages"]
        assert OpenRouterDesignModerator.IMAGE_STAGE in system["content"]
        text, image = user["content"]
        assert text == {"type": "text", "text": "Customer's request: A logo"}
        data_url = image["image_url"]["url"]
        assert data_url.startswith("data:image/png;base64,")
        with Image.open(io.BytesIO(base64.b64decode(data_url.partition(",")[2]))) as sent:
            limit = settings.DESIGN_MODERATION_IMAGE_MAX_PX
            assert sent.size == (limit, limit) and sent.mode == "RGB"
            # Transparent areas turn grey, so the white square stays visible.
            assert sent.getpixel((5, 5)) == OpenRouterDesignModerator._BACKDROP
            assert sent.getpixel((limit // 2, limit // 2)) == (255, 255, 255)


class TestNoAnswer:
    @pytest.mark.parametrize(
        "body",
        [
            _answer(True, "brand"),  # allowed, yet names a rule
            _answer(False, "none"),  # refused, yet names no rule
            _answer(False, "politics"),  # not one of the rules
            {"choices": [{"message": {"content": json.dumps({"allowed": "yes", "category": "none", "reason": "x"})}}]},
            {"choices": [{"message": {"content": "Looks fine to me."}}]},
            {"choices": []},
        ],
    )
    async def test_an_answer_that_does_not_fit_is_no_answer(self, body: dict[str, JsonValue]) -> None:
        with pytest.raises(DesignModerationUnavailableError):
            await _moderator(_Session(body=body)).check_prompt("A tiger", "Neon")

    async def test_a_provider_error_is_no_answer(self) -> None:
        with pytest.raises(DesignModerationUnavailableError, match="HTTP 503"):
            await _moderator(_Session(status=503, body={"error": "overloaded"})).check_prompt("A tiger", "Neon")

    async def test_without_a_key_nothing_is_sent(self) -> None:
        session = _Session()
        with pytest.raises(DesignModerationUnavailableError, match="OPENROUTER_API_KEY"):
            await _moderator(session, key=None).check_image(_transparent_print_file(), "A tiger")
        assert session.sent == []
