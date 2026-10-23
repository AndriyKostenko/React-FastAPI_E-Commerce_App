"""
OpenRouterImageReviewer without the network: what it sends, how it reads the
model's answer, and that anything it cannot trust counts as no answer (never
as a verdict). The real request is the opt-in live test.
"""

import json
from logging import getLogger

import pytest
from aiohttp import ClientSession
from pydantic import SecretStr

from resources import settings
from service_layer.catalogue_image_fetcher import CatalogueImageFetcher
from service_layer.image_review import ImageReviewUnavailableError
from service_layer.openrouter_image_reviewer import OpenRouterImageReviewer

DESCRIPTION = "A black tee printed with a bold white mountain range under a rising orange sun, centred on the chest."


def _body(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def _answer(**fields) -> str:
    return json.dumps({"shows_print": True, "reason": "The print is clear.", "description": DESCRIPTION} | fields)


class TestReadingTheAnswer:
    def test_an_approval_with_its_description(self) -> None:
        answer = OpenRouterImageReviewer._parse(_body(_answer()))
        assert answer.shows_print and answer.description == DESCRIPTION

    def test_json_inside_a_markdown_fence(self) -> None:
        assert OpenRouterImageReviewer._parse(_body(f"```json\n{_answer()}\n```")).shows_print

    def test_a_rejection_needs_no_description(self) -> None:
        answer = OpenRouterImageReviewer._parse(_body(_answer(shows_print=False, description="")))
        assert not answer.shows_print

    @pytest.mark.parametrize(
        "body",
        [
            _body(_answer(description="")),  # approved, but nothing to show shoppers
            _body(_answer(description="Nice tee.")),  # too short to be a description
            _body("I think it shows a print."),  # not JSON
            _body(json.dumps({"shows_print": "yes", "reason": "x", "description": DESCRIPTION})),
            {"choices": []},
            {"error": {"message": "rate limited"}},
        ],
    )
    def test_anything_else_is_no_answer(self, body: dict) -> None:
        with pytest.raises(ImageReviewUnavailableError):
            OpenRouterImageReviewer._parse(body)


class TestRequest:
    @pytest.fixture
    async def reviewer(self) -> OpenRouterImageReviewer:
        async with ClientSession() as session:
            yield OpenRouterImageReviewer(
                session=session, fetcher=CatalogueImageFetcher(session, max_bytes=1024),
                settings=settings.model_copy(update={"OPENROUTER_API_KEY": SecretStr("test-key")}),
                logger=getLogger("test"),
            )

    def test_the_photo_goes_inline_and_the_answer_is_held_to_a_schema(self, reviewer: OpenRouterImageReviewer) -> None:
        payload = reviewer._payload("data:image/jpeg;base64,AAAA", "Mountain Tee")
        content = payload["messages"][1]["content"]
        assert content[1] == {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAAA"}}
        assert payload["response_format"]["json_schema"]["strict"] is True
        assert payload["model"] == settings.OPENROUTER_REVIEW_MODEL and payload["temperature"] == 0

    async def test_a_photo_off_the_supplier_cdn_is_never_fetched(self, reviewer: OpenRouterImageReviewer) -> None:
        with pytest.raises(ImageReviewUnavailableError, match="Not a supplier CDN URL"):
            await reviewer.review("http://169.254.169.254/latest/meta-data", "tee")

    async def test_without_a_key_there_is_no_answer(self) -> None:
        async with ClientSession() as session:
            keyless = OpenRouterImageReviewer(
                session=session, fetcher=CatalogueImageFetcher(session, max_bytes=1024),
                settings=settings.model_copy(update={"OPENROUTER_API_KEY": None}), logger=getLogger("test"),
            )
            with pytest.raises(ImageReviewUnavailableError, match="OPENROUTER_API_KEY"):
                await keyless.review("https://cf.cjdropshipping.com/tee.jpg", "tee")
