"""Which supplier products may reach the store, decided from their main photo."""

from asyncio import Semaphore, gather
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from logging import Logger

from contracts.supplier import GenericSupplierProduct
from database_layer.catalogue_image_mirror_repository import CatalogueImageMirrorRepository
from database_layer.product_repository import ProductRepository
from database_layer.supplier_image_review_repository import SupplierImageReviewRepository
from infrastructure.managers.database_session_manager import DatabaseSessionManager
from service_layer.image_review import ImageReview, ImageReviewUnavailableError, ImageVerdict, ProductImageReviewer


class ImportAction(StrEnum):
    # Already in the store and never reviewed (imported before reviews
    # existed, until the one-off run reaches it): written as before.
    AS_SUPPLIED = "as_supplied"
    # Its photo was approved: written with the description the model wrote.
    DESCRIBED = "described"
    # Not written this time: photo rejected, no photo, or no answer yet.
    # A new product is not created; one already in the store is left as it is.
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ImportDecision:
    action: ImportAction
    description: str | None = None
    reason: str | None = None

    @classmethod
    def from_review(cls, verdict: str, reason: str, description: str | None) -> "ImportDecision":
        if verdict == ImageVerdict.APPROVED:
            return cls(ImportAction.DESCRIBED, description=description)
        return cls(ImportAction.SKIPPED, reason=f"photo rejected: {reason}")


@dataclass(slots=True)
class CatalogueReviewReport:
    """What a run over products already in the store found."""

    described: list[str] = field(default_factory=list)
    rejected: list[tuple[str, str, str]] = field(default_factory=list)  # pid, name, reason
    unavailable: list[tuple[str, str]] = field(default_factory=list)  # pid, reason

    def as_dict(self) -> dict[str, int]:
        return {"described": len(self.described), "rejected": len(self.rejected), "unavailable": len(self.unavailable)}


class SupplierImageReviewService:
    """
    Reviews each supplier product's main photo before an import writes it.

    A photo is reviewed once: the verdict is stored (SupplierImageReview) and
    reused on every later sync, so an approved product keeps the model's
    description instead of getting the supplier's back, and a rejected photo
    is not paid for again. Only a new product, or a reviewed product whose
    main photo the supplier changed, needs a call. With no answer (provider
    down, no key, photo unreachable) nothing is stored and the product is
    skipped, so the next sync asks again: nothing reaches the store unchecked.

    The calls run before the import's transaction, a few at a time, and their
    verdicts are committed on their own: a batch that fails afterwards does
    not lose what was already paid for.
    """

    def __init__(self, database: DatabaseSessionManager, reviewer: ProductImageReviewer,
                 logger: Logger, concurrency: int) -> None:
        self._database = database
        self._reviewer = reviewer
        self._logger = logger
        self._concurrency = concurrency

    @staticmethod
    def main_photo(product: GenericSupplierProduct) -> str | None:
        return product.image_url or (product.images[0] if product.images else None)

    async def decide(self, supplier_id: str, products: Sequence[GenericSupplierProduct]) -> dict[str, ImportDecision]:
        """pid -> what the import may do with that product."""
        pids = [product.supplier_pid for product in products if product.supplier_pid]
        async with self._database.transaction() as session:
            existing = await ProductRepository(session).existing_pids(supplier_id, pids)
            history = await SupplierImageReviewRepository(session).history(supplier_id, pids)

        decisions: dict[str, ImportDecision] = {}
        to_review: dict[tuple[str, str], str] = {}  # (pid, photo) -> product name
        for product in products:
            pid = product.supplier_pid
            if not pid:
                continue  # refused by the import itself
            reviews = history.get(pid, {})
            photo = self.main_photo(product)
            if pid in existing and not reviews:
                decisions[pid] = ImportDecision(ImportAction.AS_SUPPLIED)
            elif photo is None:
                decisions[pid] = ImportDecision(ImportAction.SKIPPED, reason="no photo to review")
            elif photo in reviews:
                kept = reviews[photo]
                decisions[pid] = ImportDecision.from_review(kept.verdict, kept.reason, kept.description)
            else:
                to_review[(pid, photo)] = product.name

        answers = await self._review_all(to_review)
        await self._record(supplier_id, answers)
        for (pid, _photo), answer in answers.items():
            decisions[pid] = (
                ImportDecision.from_review(answer.verdict, answer.reason, answer.description)
                if isinstance(answer, ImageReview)
                else ImportDecision(ImportAction.SKIPPED, reason=f"photo review unavailable, retried next sync: {answer}")
            )
        return decisions

    async def review_catalogue(self, limit: int) -> CatalogueReviewReport:
        """
        Review products already in the store that never were, up to ``limit``.

        An approved one gets the model's description; a rejected one is only
        reported (never deleted), and from then on later syncs leave it as it
        is. The photo reviewed is the supplier's URL of the main image, found
        through the catalogue copy when the image has been copied.
        """
        async with self._database.transaction() as session:
            products = await ProductRepository(session).unreviewed_supplier_products(limit)
            copied = [p.image_url for p in products if p.image_url and not p.image_url.startswith(("https://", "http://"))]
            sources = await CatalogueImageMirrorRepository(session).source_urls(copied)
            # Plain values: the session closes before the (slow) reviews run.
            work = [
                (p.supplier_id, p.pid, p.name, sources.get(p.image_url, p.image_url) if p.image_url else None)
                for p in products
            ]

        report = CatalogueReviewReport()
        to_review = {(pid, photo): name for _supplier, pid, name, photo in work if photo}
        names = {pid: name for _supplier, pid, name, _photo in work}
        for _supplier, pid, _name, photo in work:
            if not photo:
                report.unavailable.append((pid, "no photo to review"))
        answers = await self._review_all(to_review)

        supplier_of = {pid: supplier for supplier, pid, _name, _photo in work}
        async with self._database.transaction() as session:
            reviews = SupplierImageReviewRepository(session)
            products_repository = ProductRepository(session)
            for (pid, photo), answer in answers.items():
                if not isinstance(answer, ImageReview):
                    report.unavailable.append((pid, str(answer)))
                    continue
                await reviews.record(supplier_of[pid], pid, photo, answer)
                if answer.approved:
                    product = await products_repository.get_by_supplier_pid(supplier_of[pid], pid)
                    if product is not None:
                        product.description = answer.description
                    report.described.append(pid)
                else:
                    report.rejected.append((pid, names[pid], answer.reason))
        return report

    async def _review_all(self, to_review: dict[tuple[str, str], str]) -> dict[tuple[str, str], ImageReview | ImageReviewUnavailableError]:
        gate = Semaphore(self._concurrency)

        async def one(pid: str, photo: str, name: str) -> ImageReview | ImageReviewUnavailableError:
            async with gate:
                try:
                    return await self._reviewer.review(photo, name)
                except ImageReviewUnavailableError as error:
                    self._logger.warning("No photo review for supplier product %s: %s", pid, error)
                    return error

        keys = list(to_review)
        results = await gather(*(one(pid, photo, to_review[(pid, photo)]) for pid, photo in keys))
        return dict(zip(keys, results, strict=True))

    async def _record(self, supplier_id: str, answers: dict[tuple[str, str], ImageReview | ImageReviewUnavailableError]) -> None:
        verdicts = [(pid, photo, answer) for (pid, photo), answer in answers.items() if isinstance(answer, ImageReview)]
        if not verdicts:
            return
        async with self._database.transaction() as session:
            repository = SupplierImageReviewRepository(session)
            for pid, photo, answer in verdicts:
                await repository.record(supplier_id, pid, photo, answer)

