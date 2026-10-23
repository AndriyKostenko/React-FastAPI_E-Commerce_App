"""
The design check inside the real generation job: real Redis (the quota and
the job's state), the real product test database (the refusal records) and
the real private test bucket. Only the two paid model calls are scripted:
the image model returns a fixed print-size PNG, as in the other generation
tests, and the moderator's verdicts come from tests/design_moderation_fakes.py.

Rules: a design is stored and signed only when both the request and the
image pass; a refused request costs no image; a refusal tells the customer
which rule, gives the generation back and leaves a record for the admins,
never the image; with no answer nothing is produced and the generation is
given back; the image is checked after the cutout, as it will be printed.
"""

import base64
import io
from collections.abc import AsyncGenerator, Callable
from logging import getLogger
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from PIL import Image, ImageDraw
from sqlalchemy import select

from contracts.artwork import GeneratedArtworkAsset, verify_artwork_asset
from exceptions.image_generation_exceptions import DesignCheckUnavailableError
from infrastructure.managers.cache_manager import CacheManager
from infrastructure.managers.test_database_session_manager import TestDatabaseSessionManager
from models.base import Base
from models.design_moderation_refusal_models import DesignModerationRefusal
from resources import create_cache_manager
from service_layer.background_removal_service import BackgroundRemover
from service_layer.design_moderation import (
    DesignModerationUnavailableError,
    DesignRefusal,
    DesignRefusalLog,
    ModerationCategory,
    ModerationStage,
)
from service_layer.design_refusal_log import DatabaseDesignRefusalLog
from service_layer.image_generation_quota import GenerationQuotaService
from service_layer.image_generation_service import ImageGenerationService
from service_layer.image_job_store import ImageJobStore
from service_layer.image_storage_service import ImageStorageService
from settings import get_settings
from storage.object_storage_provider import ObjectStorageProvider
from storage.object_store import ObjectStore, ObjectWrite
from tests.conftest import SIGNING_KEYS
from tests.design_moderation_fakes import ScriptedModerator, refused

# The Redis connection is bound to the session loop (asyncio_default_fixture_loop_scope).
pytestmark = pytest.mark.asyncio(loop_scope="session")

settings = get_settings()
PROMPT, STYLE = "A tiger made of neon lines", "Synthwave"


def _png(width: int, height: int, colour: tuple[int, int, int]) -> str:
    """A print-size design: big enough for the storage service's print checks."""
    image = Image.new("RGB", (width, height), (255, 255, 255))
    ImageDraw.Draw(image).ellipse((200, 200, width - 200, height - 200), fill=colour)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


GENERATED = _png(settings.PRINT_IMAGE_MIN_WIDTH_PX, settings.PRINT_IMAGE_MIN_HEIGHT_PX, (240, 90, 20))
CUTOUT = _png(settings.PRINT_IMAGE_MIN_WIDTH_PX, settings.PRINT_IMAGE_MIN_HEIGHT_PX, (20, 90, 240))


class _ScriptedImageModel:
    """Stands in for OpenRouterClient: the paid image call."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, prompt: str, style: str, remove_background: bool = False) -> tuple[str, str]:
        self.calls += 1
        return GENERATED, "scripted-image-model"


class _ScriptedCutout(BackgroundRemover):
    """Stands in for rembg: returns a different image, so the test can tell which one was checked."""

    async def remove(self, image_payload: str) -> str:
        assert image_payload == GENERATED
        return CUTOUT


class _RecordingStore(ObjectStore):
    """The real private bucket, noting each key written (S3 offers no cheap listing)."""

    def __init__(self, store: ObjectStore) -> None:
        self._store = store
        self.keys_written: list[str] = []

    async def put(self, obj: ObjectWrite) -> None:
        await self._store.put(obj)
        self.keys_written.append(obj.key)

    async def get(self, key: str) -> bytes | None:
        return await self._store.get(key)

    async def exists(self, key: str) -> bool:
        return await self._store.exists(key)

    async def presign_get(
        self, key: str, ttl_seconds: int, download_filename: str | None = None, content_type: str | None = None
    ) -> str:
        return await self._store.presign_get(key, ttl_seconds, download_filename, content_type)


class _UnwritableLog:
    """A refusal log whose database is down."""

    async def record(self, user_id: UUID | None, prompt: str, style: str, refusal: DesignRefusal) -> None:
        raise ConnectionError("database unreachable")


class _Generation:
    """One customer's generation job, wired as the worker wires it."""

    def __init__(
        self,
        db: TestDatabaseSessionManager,
        cache: CacheManager,
        moderator: ScriptedModerator,
        refusal_log: DesignRefusalLog | None = None,
    ) -> None:
        self.db = db
        self.cache = cache
        self.moderator = moderator
        self.user_id = uuid4()
        self.image_model = _ScriptedImageModel()
        self.store = _RecordingStore(ObjectStorageProvider(settings).private())
        self.quota = GenerationQuotaService(cache_manager=cache, settings=settings, logger=getLogger("test"))
        self.service = ImageGenerationService(
            quota_service=self.quota,
            job_store=ImageJobStore(cache_manager=cache, logger=getLogger("test")),
            openrouter_client=self.image_model,  # type: ignore[arg-type]
            storage_service=ImageStorageService(logger=getLogger("test"), settings=settings, store=self.store),
            background_remover=_ScriptedCutout(),
            moderator=moderator,
            refusal_log=refusal_log or DatabaseDesignRefusalLog(db),
            settings=settings,
            logger=getLogger("test"),
        )

    async def run(self, remove_background: bool = False) -> dict:
        """Submit and run a job as the route and the worker do; the job's final state."""
        job_id = uuid4().hex
        await self.service.submit_job(job_id, user_id=self.user_id)
        await self.service.run_job(job_id, PROMPT, STYLE, remove_background=remove_background)
        return await self.service.get_job(job_id, user_id=self.user_id)

    async def generations_used(self) -> int:
        used = await self.cache.redis.get(self.quota._quota_key(self.user_id))
        return int(used or 0)

    async def refusals(self) -> list[DesignModerationRefusal]:
        async with self.db.transaction() as session:
            return list((await session.execute(select(DesignModerationRefusal))).scalars().all())


@pytest.fixture
async def db(test_database_session_manager: TestDatabaseSessionManager) -> AsyncGenerator[TestDatabaseSessionManager, None]:
    await test_database_session_manager.truncate_all_tables(Base.metadata)
    yield test_database_session_manager
    await test_database_session_manager.truncate_all_tables(Base.metadata)


@pytest.fixture
async def cache() -> AsyncGenerator[CacheManager, None]:
    manager = create_cache_manager()
    await manager.connect()
    try:
        yield manager
    finally:
        await manager.close()


# make(moderator, refusal_log=None): the log defaults to the real database one.
type MakeGeneration = Callable[..., _Generation]


@pytest.fixture
async def generation(db, cache) -> AsyncGenerator[MakeGeneration, None]:
    """Builds generation jobs, and drops their quota keys afterwards."""
    made: list[_Generation] = []

    def make(moderator: ScriptedModerator, refusal_log: DesignRefusalLog | None = None) -> _Generation:
        made.append(_Generation(db, cache, moderator, refusal_log))
        return made[-1]

    yield make
    for job in made:
        await cache.redis.delete(job.quota._quota_key(job.user_id))


class TestAPassingDesign:
    async def test_is_stored_signed_and_counted(self, generation) -> None:
        job = generation(ScriptedModerator())

        state = await job.run()

        assert state["status"] == "completed"
        asset = GeneratedArtworkAsset.model_validate(state["design_asset"])
        assert verify_artwork_asset(asset, settings.ARTWORK_SIGNING_KEY)
        assert job.store.keys_written == [asset.key] and await job.store.exists(asset.key)
        assert job.moderator.prompts_seen == [(PROMPT, STYLE)]
        assert job.moderator.images_seen == [GENERATED]
        assert await job.generations_used() == 1
        assert await job.refusals() == []

    async def test_its_image_is_checked_as_it_will_be_printed_after_the_cutout(self, generation) -> None:
        job = generation(ScriptedModerator())

        state = await job.run(remove_background=True)

        assert state["status"] == "completed"
        assert job.moderator.images_seen == [CUTOUT]


class TestARefusedDesign:
    async def test_a_refused_request_costs_no_image_and_names_the_rule(self, generation) -> None:
        job = generation(ScriptedModerator(prompt=refused(ModerationStage.PROMPT, ModerationCategory.CHARACTER,
                                                          "It asks for Mickey Mouse.")))

        state = await job.run()

        assert state == state | {"status": "failed", "error": ModerationCategory.CHARACTER.customer_message}
        assert job.image_model.calls == 0 and job.moderator.images_seen == []
        assert job.store.keys_written == []
        assert await job.generations_used() == 0
        [record] = await job.refusals()
        assert (record.user_id, record.stage, record.category) == (job.user_id, "prompt", "character")
        assert (record.prompt, record.style, record.reason) == (PROMPT, STYLE, "It asks for Mickey Mouse.")
        assert record.model == "scripted-moderator"

    async def test_a_refused_image_is_never_stored(self, generation) -> None:
        job = generation(ScriptedModerator(image=refused(ModerationStage.IMAGE, ModerationCategory.BRAND)))

        state = await job.run()

        assert state == state | {"status": "failed", "error": ModerationCategory.BRAND.customer_message}
        assert job.image_model.calls == 1
        assert job.store.keys_written == []
        assert await job.generations_used() == 0
        [record] = await job.refusals()
        assert (record.stage, record.category) == ("image", "brand")

    async def test_stays_refused_when_its_record_cannot_be_kept(self, generation) -> None:
        job = generation(ScriptedModerator(image=refused(ModerationStage.IMAGE)), refusal_log=_UnwritableLog())

        state = await job.run()

        assert state == state | {"status": "failed", "error": ModerationCategory.BRAND.customer_message}
        assert job.store.keys_written == []
        assert await job.generations_used() == 0


class TestNoAnswer:
    @pytest.mark.parametrize("stage", [ModerationStage.PROMPT, ModerationStage.IMAGE])
    async def test_nothing_is_produced_and_the_generation_is_given_back(self, generation, stage) -> None:
        down = DesignModerationUnavailableError("OpenRouter answered HTTP 503")
        job = generation(ScriptedModerator(**{stage.value: down}))

        state = await job.run()

        assert state == state | {"status": "failed", "error": DesignCheckUnavailableError().detail}
        assert job.image_model.calls == (0 if stage is ModerationStage.PROMPT else 1)
        assert job.store.keys_written == []
        assert await job.generations_used() == 0
        assert await job.refusals() == []


class TestTheAdminRecord:
    """GET /admin/design-refusals, as AdminJS reads it through the gateway."""

    PATH = "/api/v1/admin/design-refusals"

    async def _refuse(self, db: TestDatabaseSessionManager, category: ModerationCategory, prompt: str) -> None:
        await DatabaseDesignRefusalLog(db).record(
            uuid4(), prompt, STYLE, refused(ModerationStage.PROMPT, category)
        )

    async def test_lists_refusals_newest_first_and_filters_by_rule(
        self, integration_client: AsyncClient, test_database_session_manager: TestDatabaseSessionManager
    ) -> None:
        await self._refuse(test_database_session_manager, ModerationCategory.BRAND, "first")
        await self._refuse(test_database_session_manager, ModerationCategory.CHARACTER, "second")

        listed = (await integration_client.get(self.PATH)).json()
        assert [row["prompt"] for row in listed] == ["second", "first"]

        brands = (await integration_client.get(self.PATH, params={"category": "brand"})).json()
        assert [row["prompt"] for row in brands] == ["first"]

        one = await integration_client.get(f"{self.PATH}/{listed[0]['id']}")
        assert one.status_code == 200 and one.json()["category"] == "character"

        fields = (await integration_client.get("/api/v1/admin/schema/design-refusals")).json()["fields"]
        assert {field["path"] for field in fields} >= {"category", "stage", "prompt", "reason", "user_id"}

    async def test_only_admins_may_read_them(self, integration_client: AsyncClient) -> None:
        customer = SIGNING_KEYS.caller_auth(user_id=uuid4(), role="user")
        response = await integration_client.get(self.PATH, auth=customer)
        assert response.status_code == 403
