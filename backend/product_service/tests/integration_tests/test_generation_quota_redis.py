"""GenerationQuotaService against the real Redis — the refund is a Lua script, so mocks prove little."""
from logging import getLogger
from uuid import uuid4

import pytest

from resources import create_cache_manager
from service_layer.image_generation_quota import GenerationQuotaService
from shared.settings import get_settings

# Fixtures run on the session loop (asyncio_default_fixture_loop_scope); the
# Redis connection is bound to it, so the tests must share that loop.
pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
async def quota():
    cache = create_cache_manager()
    await cache.connect()
    service = GenerationQuotaService(cache_manager=cache, settings=get_settings(), logger=getLogger("test"))
    user_id = uuid4()
    try:
        yield service, cache, user_id
    finally:
        # A throwaway user id keeps real users untouched; drop its key anyway.
        await cache.redis.delete(service._quota_key(user_id))
        await cache.close()


async def test_refund_gives_one_generation_back(quota):
    service, _, user_id = quota
    limit = get_settings().PRODUCT_IMAGE_GENERATION_LIMIT

    assert await service.consume(user_id) == limit - 1
    assert await service.consume(user_id) == limit - 2
    await service.refund(user_id)

    # The next consume sees the refunded slot.
    assert await service.consume(user_id) == limit - 2


async def test_refund_never_goes_below_zero(quota):
    service, cache, user_id = quota

    await service.refund(user_id)          # nothing spent yet
    await service.refund(user_id)

    assert await cache.redis.get(service._quota_key(user_id)) is None
    assert await service.consume(user_id) == get_settings().PRODUCT_IMAGE_GENERATION_LIMIT - 1


async def test_refund_keeps_the_window(quota):
    service, cache, user_id = quota
    key = service._quota_key(user_id)

    await service.consume(user_id)
    await service.consume(user_id)
    ttl_before = await cache.redis.ttl(key)
    await service.refund(user_id)

    ttl_after = await cache.redis.ttl(key)
    assert 0 < ttl_after <= ttl_before
