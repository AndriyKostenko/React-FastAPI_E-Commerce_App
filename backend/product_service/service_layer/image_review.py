"""What a supplier product's photo review decides, and the port a reviewer implements."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ImageVerdict(StrEnum):
    # The photo clearly shows what is printed on the T-shirt.
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ImageReview:
    """One reviewer's answer about one photo."""

    verdict: ImageVerdict
    reason: str
    # Written from the photo; set only when approved, and then it replaces the supplier's.
    description: str | None
    model: str

    @property
    def approved(self) -> bool:
        return self.verdict is ImageVerdict.APPROVED


class ImageReviewUnavailableError(Exception):
    """No answer this time (provider down, timeout, no key, unreadable image or answer).

    Nothing is recorded, so the product is reviewed again on the next sync.
    """


class ProductImageReviewer(Protocol):
    """Looks at a supplier product's main photo before it reaches the store."""

    async def review(self, image_url: str, product_name: str) -> ImageReview:
        """Raises ImageReviewUnavailableError when there is no answer this time."""
        ...
