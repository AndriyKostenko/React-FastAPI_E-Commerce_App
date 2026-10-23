"""
A photo reviewer with scripted verdicts, standing in for the paid OpenRouter
call in the import and catalogue tests (agreed with the owner). Everything
around it (the decisions, the stored reviews, the import) runs for real; the
OpenRouter request itself is covered by the opt-in live test.
"""

from logging import getLogger

from infrastructure.managers.database_session_manager import DatabaseSessionManager
from service_layer.image_review import ImageReview, ImageReviewUnavailableError, ImageVerdict
from service_layer.supplier_image_review_service import SupplierImageReviewService

APPROVED_DESCRIPTION = (
    "A black crew-neck T-shirt printed across the chest with a bold white mountain range "
    "under a rising orange sun."
)


def approved(description: str = APPROVED_DESCRIPTION) -> ImageReview:
    return ImageReview(verdict=ImageVerdict.APPROVED, reason="The print is clear and centred.",
                       description=description, model="scripted")


def rejected(reason: str = "The photo is a size chart; no print is visible.") -> ImageReview:
    return ImageReview(verdict=ImageVerdict.REJECTED, reason=reason, description=None, model="scripted")


class ScriptedReviewer:
    """Answers each photo URL as scripted (approved by default) and records what it was asked."""

    def __init__(self, answers: dict[str, ImageReview | ImageReviewUnavailableError] | None = None,
                 default: ImageReview | ImageReviewUnavailableError | None = None) -> None:
        self._answers = answers or {}
        self._default = default if default is not None else approved()
        self.asked: list[str] = []

    async def review(self, image_url: str, product_name: str) -> ImageReview:
        self.asked.append(image_url)
        answer = self._answers.get(image_url, self._default)
        if isinstance(answer, ImageReviewUnavailableError):
            raise answer
        return answer


def review_service(database: DatabaseSessionManager, reviewer: ScriptedReviewer | None = None) -> SupplierImageReviewService:
    return SupplierImageReviewService(database=database, reviewer=reviewer or ScriptedReviewer(),
                                      logger=getLogger("test"), concurrency=2)
