from src.cache import LRUCache, RedisCache, cache_key, normalize_goal


def test_normalize_goal_lowercases_strips_and_collapses_whitespace():
    assert normalize_goal("  Learn   Python  ") == "learn python"
    assert normalize_goal("LEARN\tPYTHON\n") == "learn python"


def test_cache_key_is_deterministic_and_normalization_sensitive():
    assert cache_key("Learn Python") == cache_key("  learn   python  ")
    assert cache_key("Learn Python") != cache_key("Learn Guitar")
    assert len(cache_key("Learn Python")) == 64  # sha256 hex digest


async def test_lru_cache_set_and_get_roundtrip():
    cache = LRUCache()
    await cache.set("k1", "v1")
    assert await cache.get("k1") == "v1"


async def test_lru_cache_missing_key_returns_none():
    cache = LRUCache()
    assert await cache.get("missing") is None


async def test_lru_cache_expired_entry_returns_none():
    cache = LRUCache()
    await cache.set("k1", "v1", ttl=-1)  # already expired
    assert await cache.get("k1") is None


async def test_lru_cache_evicts_oldest_when_over_capacity():
    cache = LRUCache(maxsize=2)
    await cache.set("a", "1")
    await cache.set("b", "2")
    await cache.set("c", "3")  # should evict "a"
    assert await cache.get("a") is None
    assert await cache.get("b") == "2"
    assert await cache.get("c") == "3"


async def test_lru_cache_get_refreshes_recency():
    cache = LRUCache(maxsize=2)
    await cache.set("a", "1")
    await cache.set("b", "2")
    await cache.get("a")  # "a" is now most-recently-used
    await cache.set("c", "3")  # should evict "b", not "a"
    assert await cache.get("b") is None
    assert await cache.get("a") == "1"
    assert await cache.get("c") == "3"


class _BrokenRedisClient:
    async def get(self, key):
        raise ConnectionError("redis unreachable")

    async def set(self, key, value, ex=None):
        raise ConnectionError("redis unreachable")


class _FakeRedisClient:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value.encode() if isinstance(value, str) else value


async def test_redis_cache_happy_path_does_not_touch_fallback():
    fallback = LRUCache()
    redis_cache = RedisCache("redis://fake", fallback)
    redis_cache._client = _FakeRedisClient()

    await redis_cache.set("k", "v")
    assert await redis_cache.get("k") == "v"
    assert redis_cache._broken is False
    # Fallback was never used on the happy path.
    assert await fallback.get("k") is None


async def test_redis_cache_degrades_to_fallback_on_set_failure_and_never_crashes():
    fallback = LRUCache()
    redis_cache = RedisCache("redis://fake", fallback)
    redis_cache._client = _BrokenRedisClient()

    # Must not raise, even though the underlying client always raises.
    await redis_cache.set("k", "v")
    assert redis_cache._broken is True
    assert await fallback.get("k") == "v"


async def test_redis_cache_degrades_to_fallback_on_get_failure_and_never_crashes():
    fallback = LRUCache()
    await fallback.set("k", "pre-seeded")
    redis_cache = RedisCache("redis://fake", fallback)
    redis_cache._client = _BrokenRedisClient()

    result = await redis_cache.get("k")
    assert result == "pre-seeded"
    assert redis_cache._broken is True


async def test_redis_cache_stays_broken_after_first_failure_no_retry_storm():
    fallback = LRUCache()
    redis_cache = RedisCache("redis://fake", fallback)
    redis_cache._client = _BrokenRedisClient()

    await redis_cache.get("k")
    assert redis_cache._broken is True

    # Swap in a working client - RedisCache should stay degraded rather
    # than immediately trying it again mid-request.
    redis_cache._client = _FakeRedisClient()
    await redis_cache.set("k2", "v2")
    assert await fallback.get("k2") == "v2"
