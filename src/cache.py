"""Roadmap response cache.

Two backends behind a common async interface:
- LRUCache: in-process, always available, used by default.
- RedisCache: used only when REDIS_URL is set. Degrades permanently to the
  in-process LRU for the rest of the process lifetime the first time a
  Redis call fails, so a flaky/unreachable Redis never fails a request.

Cache key = sha256(normalize(goal)); normalize = lowercase, strip, collapse
internal whitespace. TTL is 30 days.
"""

import hashlib
import os
import re
import time
from collections import OrderedDict
from typing import Optional, Protocol

import structlog

logger = structlog.get_logger(__name__)

TTL_SECONDS = 30 * 24 * 3600
DEFAULT_LRU_MAXSIZE = 256

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_goal(goal: str) -> str:
    return _WHITESPACE_RE.sub(" ", goal.strip().lower())


def cache_key(goal: str) -> str:
    return hashlib.sha256(normalize_goal(goal).encode("utf-8")).hexdigest()


class CacheBackend(Protocol):
    async def get(self, key: str) -> Optional[str]: ...

    async def set(self, key: str, value: str, ttl: int = TTL_SECONDS) -> None: ...


class LRUCache:
    """In-process LRU cache with per-entry TTL. Always available."""

    def __init__(self, maxsize: int = DEFAULT_LRU_MAXSIZE):
        self._data: "OrderedDict[str, tuple[float, str]]" = OrderedDict()
        self._maxsize = maxsize

    async def get(self, key: str) -> Optional[str]:
        entry = self._data.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at < time.time():
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return value

    async def set(self, key: str, value: str, ttl: int = TTL_SECONDS) -> None:
        self._data[key] = (time.time() + ttl, value)
        self._data.move_to_end(key)
        while len(self._data) > self._maxsize:
            self._data.popitem(last=False)


class RedisCache:
    """Redis-backed cache that falls back to an in-process LRU on any
    connection or command failure. Once broken, stays on the fallback for
    the rest of the process lifetime (no retry storms against a dead
    Redis)."""

    def __init__(self, redis_url: str, fallback: CacheBackend):
        self._redis_url = redis_url
        self._fallback = fallback
        self._client = None
        self._broken = False

    async def _get_client(self):
        if self._client is None:
            import redis.asyncio as redis_asyncio

            self._client = redis_asyncio.from_url(
                self._redis_url, socket_connect_timeout=1, socket_timeout=1
            )
        return self._client

    def _degrade(self, error: Exception) -> None:
        if not self._broken:
            logger.warning("cache.redis_unavailable_degrading_to_memory", error=str(error))
        self._broken = True

    async def get(self, key: str) -> Optional[str]:
        if self._broken:
            return await self._fallback.get(key)
        try:
            client = await self._get_client()
            value = await client.get(key)
            return value.decode("utf-8") if value is not None else None
        except Exception as e:
            self._degrade(e)
            return await self._fallback.get(key)

    async def set(self, key: str, value: str, ttl: int = TTL_SECONDS) -> None:
        if self._broken:
            await self._fallback.set(key, value, ttl)
            return
        try:
            client = await self._get_client()
            await client.set(key, value, ex=ttl)
        except Exception as e:
            self._degrade(e)
            await self._fallback.set(key, value, ttl)


def build_cache() -> CacheBackend:
    redis_url = os.getenv("REDIS_URL")
    lru = LRUCache()
    if redis_url:
        return RedisCache(redis_url, lru)
    return lru


# Module-level singleton used by the app.
cache: CacheBackend = build_cache()
