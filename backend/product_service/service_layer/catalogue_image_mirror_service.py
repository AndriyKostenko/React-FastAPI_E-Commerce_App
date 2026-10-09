"""
Copies supplier (CJ) catalogue images into the catalogue object store.

The storefront stops depending on CJ's CDN: once an image is copied, every
product, gallery image and variant that used its URL holds the object key
instead, and the supplier sync keeps writing the key on later runs
(``ProductService`` translates incoming URLs through the mirror table).

A run, under an advisory lock so two never overlap:
  1. read   -- which supplier URLs are still in use and due a (re)try;
  2. remote -- per URL, download and store the object, no transaction open;
  3. write  -- per URL, one short transaction: record the mirror and rewrite
               the rows using the URL.
A URL that cannot be copied keeps being served from CJ; it is retried with a
growing delay and given up on after CATALOGUE_IMAGE_MIRROR_MAX_ATTEMPTS.
"""

import hashlib
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from logging import Logger

from sqlalchemy import text

from database_layer.catalogue_image_mirror_repository import CatalogueImageMirrorRepository
from models.catalogue_image_mirror_models import CatalogueImageMirror, MirrorStatus
from service_layer.catalogue_image_fetcher import CatalogueImageFetchError, CatalogueImageFetcher, FetchedImage
from shared.managers.cache_manager import CacheManager
from shared.managers.database_session_manager import DatabaseSessionManager
from shared.settings import Settings
from storage.object_store import ObjectStorageError, ObjectStore, ObjectWrite

# pg_try_advisory_lock key: "cimirror" as ASCII. One run at a time, across
# every worker process.
_MIRROR_LOCK_KEY = 0x63696D6972726F72


@dataclass(slots=True)
class MirrorReport:
    in_use: int = 0          # supplier URLs still referenced by the catalogue
    attempted: int = 0       # URLs due this run (capped by the batch size)
    mirrored: int = 0        # newly copied
    rows_rewritten: int = 0  # catalogue rows now holding a key
    failed: int = 0          # this run's failures (retried later unless given up)
    given_up: int = 0        # marked failed for good this run
    skipped_already_running: bool = False

    def as_dict(self) -> dict[str, int | bool]:
        return asdict(self)


class MirrorRetryPolicy:
    """15 min after the first failure, doubling, at most a day apart."""

    BASE = timedelta(minutes=15)
    CEILING = timedelta(hours=24)

    @classmethod
    def is_due(cls, mirror: CatalogueImageMirror | None, now: datetime) -> bool:
        if mirror is None or mirror.status == MirrorStatus.MIRRORED.value:
            # Never tried; or copied but still referenced (a sync wrote the URL
            # while the copy was being recorded) -- only the rewrite is left.
            return True
        if mirror.attempts == 0 or mirror.last_attempt_at is None:
            return True
        delay = min(cls.BASE * (2 ** (mirror.attempts - 1)), cls.CEILING)
        return mirror.last_attempt_at + delay <= now


class CatalogueImageMirrorService:
    KEY_PREFIX = "catalogue/cj"
    CACHE_CONTROL = "public, max-age=31536000, immutable"

    def __init__(
        self,
        database: DatabaseSessionManager,
        store: ObjectStore,
        fetcher: CatalogueImageFetcher,
        cache_manager: CacheManager,
        settings: Settings,
        logger: Logger,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._database = database
        self._store = store
        self._fetcher = fetcher
        self._cache = cache_manager
        self._batch = settings.CATALOGUE_IMAGE_MIRROR_BATCH
        self._max_attempts = settings.CATALOGUE_IMAGE_MIRROR_MAX_ATTEMPTS
        self._logger = logger
        self._now = clock or (lambda: datetime.now(UTC))

    @classmethod
    def object_key(cls, source_url: str, extension: str) -> str:
        """Derived from the URL, so the same image is stored once however
        many products use it, and a retry overwrites rather than duplicates."""
        digest = hashlib.sha256(source_url.encode()).hexdigest()
        return f"{cls.KEY_PREFIX}/{digest[:2]}/{digest}.{extension}"

    async def mirror_pending(self) -> MirrorReport:
        report = MirrorReport()
        engine = self._database.async_engine
        assert engine is not None
        # A session-level advisory lock lives on one connection, so it is held
        # on a dedicated one for the whole run and released explicitly.
        async with engine.connect() as lock_connection:
            locked = await lock_connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": _MIRROR_LOCK_KEY})
            if not locked:
                report.skipped_already_running = True
                self._logger.info("Catalogue image mirror skipped: the previous run is still going")
                return report
            try:
                await self._run(report)
            finally:
                await lock_connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _MIRROR_LOCK_KEY})
                await lock_connection.commit()

        if report.rows_rewritten:
            try:
                await self._cache.invalidate_namespace(namespace="products")
            except Exception:
                # The rows are committed; a stale cached page still shows the
                # CJ URL, which works, until its TTL runs out.
                self._logger.exception("Catalogue images mirrored but product cache invalidation failed")
        self._logger.info("Catalogue image mirror finished: %s", report.as_dict())
        return report

    async def _run(self, report: MirrorReport) -> None:
        # 1. read
        now = self._now()
        async with self._database.transaction() as session:
            repository = CatalogueImageMirrorRepository(session)
            urls = await repository.external_urls_in_use()
            known = await repository.get_by_source_urls(urls)
        report.in_use = len(urls)
        due = [url for url in urls if MirrorRetryPolicy.is_due(known.get(url), now)][: self._batch]
        report.attempted = len(due)

        for url in due:
            mirror = known.get(url)
            if mirror is not None and mirror.status == MirrorStatus.MIRRORED.value and mirror.object_key:
                report.rows_rewritten += await self._rewrite(url, mirror.object_key)
                continue
            # 2. remote
            try:
                fetched = await self._fetcher.fetch(url)
                key = self.object_key(url, fetched.image.extension)
                await self._store.put(self._object_for(key, fetched))
            except (CatalogueImageFetchError, ObjectStorageError) as error:
                permanent = isinstance(error, CatalogueImageFetchError) and error.permanent
                if await self._record_failure(url, str(error), permanent):
                    report.given_up += 1
                report.failed += 1
                continue
            # 3. write
            report.rows_rewritten += await self._record_success(url, key, fetched)
            report.mirrored += 1

    def _object_for(self, key: str, fetched: FetchedImage) -> ObjectWrite:
        return ObjectWrite(
            key=key,
            body=fetched.content,
            content_type=fetched.image.content_type,
            cache_control=self.CACHE_CONTROL,
            sha256=hashlib.sha256(fetched.content).hexdigest(),
        )

    async def _record_success(self, url: str, key: str, fetched: FetchedImage) -> int:
        now = self._now()
        async with self._database.transaction() as session:
            repository = CatalogueImageMirrorRepository(session)
            mirror = await self._locked_row(repository, url)
            mirror.status = MirrorStatus.MIRRORED.value
            mirror.object_key = key
            mirror.content_type = fetched.image.content_type
            mirror.size_bytes = len(fetched.content)
            mirror.sha256 = hashlib.sha256(fetched.content).hexdigest()
            mirror.attempts += 1
            mirror.last_attempt_at = now
            mirror.mirrored_at = now
            mirror.last_error = None
            await session.flush()
            # Same transaction: no row can be left pointing at a URL whose
            # mirror says it is copied, nor at a key with no mirror behind it.
            return await repository.rewrite_references(url, key)

    async def _record_failure(self, url: str, error: str, permanent: bool) -> bool:
        """Record a failed attempt; True when this one gives the URL up."""
        async with self._database.transaction() as session:
            repository = CatalogueImageMirrorRepository(session)
            mirror = await self._locked_row(repository, url)
            mirror.attempts += 1
            mirror.last_attempt_at = self._now()
            mirror.last_error = error[:1000]
            given_up = permanent or mirror.attempts >= self._max_attempts
            if given_up:
                mirror.status = MirrorStatus.FAILED.value
                self._logger.warning(
                    "Gave up copying catalogue image %s after %d attempt(s); it stays served from the supplier: %s",
                    url, mirror.attempts, error,
                )
            else:
                self._logger.info("Copying catalogue image %s failed (attempt %d): %s", url, mirror.attempts, error)
            return given_up

    async def _rewrite(self, url: str, key: str) -> int:
        async with self._database.transaction() as session:
            return await CatalogueImageMirrorRepository(session).rewrite_references(url, key)

    @staticmethod
    async def _locked_row(repository: CatalogueImageMirrorRepository, url: str) -> CatalogueImageMirror:
        mirror = await repository.get_for_update(url)
        if mirror is None:
            mirror = await repository.create(
                CatalogueImageMirror(source_url=url, status=MirrorStatus.PENDING.value, attempts=0)
            )
        return mirror
