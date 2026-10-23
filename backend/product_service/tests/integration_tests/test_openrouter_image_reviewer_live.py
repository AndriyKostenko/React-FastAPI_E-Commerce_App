"""
One real OpenRouter review, opt-in: it costs a call, so it runs only when
OPENROUTER_LIVE_REVIEW_IMAGE_URL names a CJ product photo and the service
has an OpenRouter key (never in CI). For example:

    OPENROUTER_LIVE_REVIEW_IMAGE_URL=https://cf.cjdropshipping.com/... \
        ./local/dev.sh test product_service -k live_review
"""

import os
from logging import getLogger

import pytest
from aiohttp import ClientSession

from resources import settings
from service_layer.catalogue_image_fetcher import CatalogueImageFetcher
from service_layer.image_review import ImageVerdict
from service_layer.openrouter_image_reviewer import OpenRouterImageReviewer

IMAGE_URL = os.environ.get("OPENROUTER_LIVE_REVIEW_IMAGE_URL")

pytestmark = pytest.mark.skipif(
    not IMAGE_URL or settings.OPENROUTER_API_KEY is None,
    reason="opt-in: set OPENROUTER_LIVE_REVIEW_IMAGE_URL (and an OpenRouter key)",
)


async def test_live_review_returns_a_verdict_the_import_can_use() -> None:
    async with ClientSession() as session:
        reviewer = OpenRouterImageReviewer(
            session=session,
            fetcher=CatalogueImageFetcher(session, max_bytes=settings.CATALOGUE_IMAGE_MAX_BYTES),
            settings=settings,
            logger=getLogger("test"),
        )
        review = await reviewer.review(IMAGE_URL, "T-shirt")
    assert review.verdict in (ImageVerdict.APPROVED, ImageVerdict.REJECTED)
    assert review.model == settings.OPENROUTER_REVIEW_MODEL and review.reason
    if review.approved:
        assert review.description and len(review.description) >= 40
    else:
        assert review.description is None
