"""
Real OpenRouter moderation calls, opt-in: they cost three calls, so they run
only when OPENROUTER_LIVE_MODERATION=1 and the service has an OpenRouter key
(never in CI). For example:

    OPENROUTER_LIVE_MODERATION=1 ./local/dev.sh test product_service -k live_moderation
"""

import base64
import io
import os
from logging import getLogger

import pytest
from aiohttp import ClientSession
from PIL import Image, ImageDraw

from resources import settings
from service_layer.design_moderation import ModerationCategory, ModerationStage
from service_layer.openrouter_design_moderator import OpenRouterDesignModerator

pytestmark = pytest.mark.skipif(
    os.environ.get("OPENROUTER_LIVE_MODERATION") != "1" or settings.OPENROUTER_API_KEY is None,
    reason="opt-in: set OPENROUTER_LIVE_MODERATION=1 (and an OpenRouter key)",
)


def _plain_design() -> str:
    image = Image.new("RGBA", (1200, 1200), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((200, 200, 1000, 1000), fill=(230, 80, 30, 255))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


async def test_live_moderation_allows_an_original_request_and_refuses_a_brand() -> None:
    async with ClientSession() as session:
        moderator = OpenRouterDesignModerator(session=session, settings=settings, logger=getLogger("test"))
        assert await moderator.check_prompt("A tiger made of glowing neon lines", "Synthwave") is None
        refusal = await moderator.check_prompt("The Nike swoosh logo in shiny gold", "Minimalist")
    assert refusal is not None
    assert (refusal.stage, refusal.category) == (ModerationStage.PROMPT, ModerationCategory.BRAND)
    assert refusal.reason


async def test_live_moderation_allows_a_plain_image() -> None:
    async with ClientSession() as session:
        moderator = OpenRouterDesignModerator(session=session, settings=settings, logger=getLogger("test"))
        assert await moderator.check_image(_plain_design(), "An orange circle") is None
