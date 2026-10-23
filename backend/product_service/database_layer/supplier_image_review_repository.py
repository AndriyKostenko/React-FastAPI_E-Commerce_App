from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.supplier_image_review_models import SupplierImageReview
from service_layer.image_review import ImageReview
from infrastructure.database_layer.database_layer import BaseRepository


class SupplierImageReviewRepository(BaseRepository[SupplierImageReview]):
    """The verdicts on supplier product photos, one per photo URL."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, SupplierImageReview)

    async def history(self, supplier_id: str, pids: Iterable[str]) -> dict[str, dict[str, SupplierImageReview]]:
        """Every review of these products: pid -> photo URL -> review."""
        wanted = list(dict.fromkeys(pids))
        if not wanted:
            return {}
        result = await self.session.execute(
            select(SupplierImageReview).where(
                SupplierImageReview.supplier_id == supplier_id, SupplierImageReview.pid.in_(wanted)
            )
        )
        history: dict[str, dict[str, SupplierImageReview]] = {}
        for review in result.scalars().all():
            history.setdefault(review.pid, {})[review.image_url] = review
        return history

    async def record(self, supplier_id: str, pid: str, image_url: str, review: ImageReview) -> None:
        """Keep a verdict; a concurrent run that already kept one for this photo wins."""
        await self.session.execute(
            insert(SupplierImageReview)
            .values(supplier_id=supplier_id, pid=pid, image_url=image_url, verdict=review.verdict.value,
                    reason=review.reason, description=review.description, model=review.model)
            .on_conflict_do_nothing(constraint="uq_supplier_image_reviews_photo")
        )
