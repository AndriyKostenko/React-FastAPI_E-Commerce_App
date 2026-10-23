"""Asks an OpenRouter vision model whether a supplier photo clearly shows the print."""

import base64
from logging import Logger

from aiohttp import ClientSession
from pydantic import BaseModel, Field, JsonValue, model_validator
from service_layer.catalogue_image_fetcher import (
    CatalogueImageFetcher,
    CatalogueImageFetchError,
)
from service_layer.image_review import (
    ImageReview,
    ImageReviewUnavailableError,
    ImageVerdict,
)
from service_layer.openrouter_structured_chat import (
    OpenRouterStructuredChat,
    StructuredAnswerUnavailableError,
)
from settings import Settings


class _ModelAnswer(BaseModel):
    """The JSON the model must return; anything else counts as no answer."""

    # Strict: "yes" or 1 is not the boolean the schema asks for.
    shows_print: bool = Field(strict=True)
    reason: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=1500)

    @model_validator(mode="after")
    def _approved_answers_carry_a_description(self) -> "_ModelAnswer":
        self.reason = self.reason.strip()
        self.description = self.description.strip()
        if self.shows_print and len(self.description) < 40:
            raise ValueError(
                "an approved photo needs a description of at least 40 characters"
            )
        return self


class OpenRouterImageReviewer:
    """
    A ProductImageReviewer backed by an OpenRouter chat model with vision.

    The photo is downloaded here (CatalogueImageFetcher: supplier CDN only,
    size-capped, type sniffed) and sent inline, so the provider never fetches
    a URL taken from the supplier, and a photo the CDN no longer serves is
    "unavailable" rather than judged on nothing. The answer is constrained to
    a JSON schema and validated; an answer that does not fit counts as no
    answer, so a confused model can neither approve nor reject a product.
    """

    SYSTEM_PROMPT = (
        "You review supplier photos for an online T-shirt shop before a product is listed.\n"
        "Decide whether the photo clearly shows what is printed on the T-shirt: the garment "
        "and its printed design are visible, in focus, not cropped off, and not hidden by "
        "overlaid text, watermarks, size charts or collages of other products. A plain "
        "shirt with no visible print does not pass.\n"
        "Suppliers often hide a design: the print area is covered by a mosaic of large "
        "square colour blocks, or blurred, or stickered over. If the print area looks like "
        "that, the photo does not pass, whatever the blocks might depict and however "
        "colourful they are; never call it pixel art. Ask yourself: could a shopper tell "
        "exactly what artwork they would receive? Only a clear yes passes.\n"
        "If it passes, write the product description shoppers will read: 2 to 4 sentences, "
        "40 to 120 words, in English, about the printed design and the garment as they "
        "appear. Describe only what is visible. Do not mention brands, sizes, materials, "
        "prices, shipping, the photo or the supplier. Plain text, no lists or markdown.\n"
        "If it does not pass, leave the description empty.\n"
        "Always give a short reason (one sentence) for the decision."
    )

    _SCHEMA: dict[str, JsonValue] = {
        "type": "object",
        "properties": {
            "shows_print": {"type": "boolean"},
            "reason": {"type": "string"},
            "description": {"type": "string"},
        },
        "required": ["shows_print", "reason", "description"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        session: ClientSession,
        fetcher: CatalogueImageFetcher,
        settings: Settings,
        logger: Logger,
    ) -> None:
        self._fetcher = fetcher
        self._chat = OpenRouterStructuredChat(
            session,
            settings,
            logger,
            model=settings.OPENROUTER_REVIEW_MODEL,
            timeout_seconds=settings.OPENROUTER_REVIEW_TIMEOUT_SECONDS,
            purpose="review",
        )

    async def review(self, image_url: str, product_name: str) -> ImageReview:
        try:
            self._chat.require_key()
        except StructuredAnswerUnavailableError as error:
            raise ImageReviewUnavailableError(str(error)) from error
        try:
            fetched = await self._fetcher.fetch(image_url)
        except CatalogueImageFetchError as error:
            raise ImageReviewUnavailableError(
                f"photo could not be fetched: {error}"
            ) from error
        data_url = f"data:{fetched.image.content_type};base64,{base64.b64encode(fetched.content).decode('ascii')}"
        try:
            body = await self._chat.post(self._payload(data_url, product_name))
        except StructuredAnswerUnavailableError as error:
            raise ImageReviewUnavailableError(str(error)) from error
        answer = self._parse(body)
        return ImageReview(
            verdict=ImageVerdict.APPROVED
            if answer.shows_print
            else ImageVerdict.REJECTED,
            reason=answer.reason,
            description=answer.description if answer.shows_print else None,
            model=self._chat.model,
        )

    def _payload(self, data_url: str, product_name: str) -> dict[str, JsonValue]:
        return self._chat.payload(
            [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        # The supplier's title, as context only: it is often keyword
                        # stuffing, so the photo decides.
                        {
                            "type": "text",
                            "text": f"Supplier's product title: {product_name[:200]}",
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            "print_review",
            self._SCHEMA,
        )

    @staticmethod
    def _parse(body: dict[str, JsonValue]) -> _ModelAnswer:
        try:
            return OpenRouterStructuredChat.parse(body, _ModelAnswer)
        except StructuredAnswerUnavailableError as error:
            raise ImageReviewUnavailableError(str(error)) from error
