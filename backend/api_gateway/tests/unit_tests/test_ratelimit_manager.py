"""Tests for the sliding-window rate limiter against an in-memory Redis double."""

from logging import getLogger
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from starlette.requests import Request

from infrastructure.exceptions.base_exceptions import RateLimitExceededError
from infrastructure.managers.ratelimit_manager import RateLimitManager

# Only for the annotation: the test imports the middleware where it builds it.
if TYPE_CHECKING:
    from middleware.cache_middleware import GatewayRequestMiddleware


TRUSTED = ["172.16.0.0/12"]


class FakePipeline:
    """Records the queued commands and applies them on execute()."""

    def __init__(self, redis: "FakeRedis") -> None:
        self._redis = redis
        self._queued = []

    def zadd(self, key, mapping):
        self._queued.append(lambda: self._redis.sets.setdefault(key, {}).update(mapping))

    def zremrangebyscore(self, key, minimum, maximum):
        def run():
            entries = self._redis.sets.setdefault(key, {})
            for member in [m for m, score in entries.items() if minimum <= score <= maximum]:
                del entries[member]
        self._queued.append(run)

    def zcard(self, key):
        self._queued.append(lambda: len(self._redis.sets.setdefault(key, {})))

    def expire(self, key, seconds):
        self._queued.append(lambda: True)

    def zrange(self, key, start, stop, withscores=False):
        def run():
            ordered = sorted(self._redis.sets.setdefault(key, {}).items(), key=lambda item: item[1])
            window = ordered[start:] if stop == -1 else ordered[start:stop + 1]
            return window if withscores else [member for member, _ in window]
        self._queued.append(run)

    async def execute(self):
        results = [command() for command in self._queued]
        self._queued.clear()
        return results


class FakeRedis:
    def __init__(self) -> None:
        self.sets: dict[str, dict[str, float]] = {}

    def pipeline(self):
        return FakePipeline(self)

    async def zrem(self, key, member):
        self.sets.setdefault(key, {}).pop(member, None)


def _manager() -> tuple[RateLimitManager, FakeRedis]:
    manager = RateLimitManager(
        service_prefix="test-service",
        redis_url="redis://unused",
        logger=getLogger("test"),
        trusted_proxy_networks=TRUSTED,
    )
    redis = FakeRedis()
    manager._redis = redis
    return manager, redis


def _request(headers: dict[str, str] | None = None, peer: str = "203.0.113.9", path: str = "/login") -> Request:
    return Request({
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [
            (key.lower().encode(), value.encode())
            for key, value in (headers or {}).items()
        ],
        "client": (peer, 51234),
        "server": ("localhost", 8001),
    })


class TestWindowAccounting:
    async def test_allows_exactly_the_configured_number_of_requests(self):
        manager, _ = _manager()
        request = _request()

        for _ in range(3):
            assert await manager.is_rate_limited(request, times=3, seconds=60) is False

        with pytest.raises(RateLimitExceededError):
            await manager.is_rate_limited(request, times=3, seconds=60)

    async def test_rejected_requests_do_not_extend_the_window(self):
        """A client hammering the endpoint must not lock itself out past `seconds`."""
        manager, redis = _manager()
        request = _request()

        for _ in range(2):
            await manager.is_rate_limited(request, times=2, seconds=60)
        for _ in range(5):
            with pytest.raises(RateLimitExceededError):
                await manager.is_rate_limited(request, times=2, seconds=60)

        key = manager._generate_rate_limit_key(request)
        assert len(redis.sets[key]) == 2

    async def test_simultaneous_requests_are_counted_separately(self):
        """Identical timestamps must not collapse into one set member."""
        manager, redis = _manager()
        request = _request()

        with patch("infrastructure.managers.ratelimit_manager.time", return_value=1_700_000_000.0):
            for _ in range(3):
                await manager.is_rate_limited(request, times=5, seconds=60)

        key = manager._generate_rate_limit_key(request)
        assert len(redis.sets[key]) == 3

    async def test_entries_are_scored_with_wall_clock_time(self):
        """Scores are shared across workers, so they must not be process-local."""
        manager, redis = _manager()
        request = _request()

        with patch("infrastructure.managers.ratelimit_manager.time", return_value=1_700_000_000.0):
            await manager.is_rate_limited(request, times=5, seconds=60)

        key = manager._generate_rate_limit_key(request)
        assert list(redis.sets[key].values()) == [1_700_000_000.0]

    async def test_expired_entries_leave_the_window(self):
        manager, _ = _manager()
        request = _request()

        with patch("infrastructure.managers.ratelimit_manager.time", return_value=1_000.0):
            for _ in range(2):
                await manager.is_rate_limited(request, times=2, seconds=60)
        with patch("infrastructure.managers.ratelimit_manager.time", return_value=1_100.0):
            assert await manager.is_rate_limited(request, times=2, seconds=60) is False


class TestKeying:
    async def test_a_spoofed_forwarded_for_shares_the_callers_bucket(self):
        """The bypass this limiter previously had: one key per forged header."""
        manager, redis = _manager()

        for index in range(5):
            request = _request({"x-forwarded-for": f"1.2.3.{index}"})
            try:
                await manager.is_rate_limited(request, times=2, seconds=60)
            except RateLimitExceededError:
                pass

        assert len(redis.sets) == 1

    async def test_a_trusted_proxy_separates_real_clients(self):
        manager, redis = _manager()

        for address in ("198.51.100.1", "198.51.100.2"):
            request = _request({"x-forwarded-for": address}, peer="172.20.0.4")
            await manager.is_rate_limited(request, times=2, seconds=60)

        assert len(redis.sets) == 2

    async def test_separate_endpoints_get_separate_windows(self):
        manager, redis = _manager()

        await manager.is_rate_limited(_request(path="/login"), times=2, seconds=60)
        await manager.is_rate_limited(_request(path="/register"), times=2, seconds=60)

        assert len(redis.sets) == 2


class TestFailureHandling:
    async def test_redis_failure_fails_open(self):
        manager, _ = _manager()

        class BrokenRedis:
            def pipeline(self):
                raise ConnectionError("redis is down")

        manager._redis = BrokenRedis()
        assert await manager.is_rate_limited(_request(), times=1, seconds=60) is False


class TestGlobalLimitHasItsOwnBucket:
    """
    The gateway middleware's global check runs on every request, before a
    route's own @rate_limited check. Both used to write the same key, so each
    request counted twice and the global 60-second window pruned the route's
    hourly one.
    """

    @staticmethod
    def _middleware(manager: RateLimitManager) -> "GatewayRequestMiddleware":
        from unittest.mock import AsyncMock, MagicMock
        from middleware.cache_middleware import GatewayRequestMiddleware

        cache = MagicMock(
            get_cached_response=AsyncMock(return_value=None),
            get_invalidation_namespaces=MagicMock(return_value=[]),
        )
        return GatewayRequestMiddleware(cache_manager=cache, rate_limit_manager=manager)

    async def test_route_limit_counts_each_request_once(self):
        from starlette.responses import Response

        manager, _ = _manager()
        middleware = self._middleware(manager)

        async def route(request: Request) -> Response:
            # What @rate_limited(times=5, seconds=3600) does inside the route.
            await manager.is_rate_limited(request, times=5, seconds=3600)
            return Response(status_code=200)

        for _ in range(5):
            response = await middleware(_request(path="/users/me/password"), route, is_cacheable=False)
            assert response.status_code == 200
        with pytest.raises(RateLimitExceededError):
            await middleware(_request(path="/users/me/password"), route, is_cacheable=False)

    async def test_global_window_does_not_prune_an_hourly_route_window(self):
        from starlette.responses import Response

        manager, _ = _manager()
        middleware = self._middleware(manager)

        async def route(request: Request) -> Response:
            await manager.is_rate_limited(request, times=2, seconds=3600)
            return Response(status_code=200)

        # Two requests ten minutes apart use up the hourly allowance; the
        # global check's 60-second prune in between must not forget the first.
        with patch("infrastructure.managers.ratelimit_manager.time", return_value=1_000.0):
            await middleware(_request(path="/login"), route, is_cacheable=False)
        with patch("infrastructure.managers.ratelimit_manager.time", return_value=1_600.0):
            await middleware(_request(path="/login"), route, is_cacheable=False)
        with patch("infrastructure.managers.ratelimit_manager.time", return_value=1_700.0):
            with pytest.raises(RateLimitExceededError):
                await middleware(_request(path="/login"), route, is_cacheable=False)
