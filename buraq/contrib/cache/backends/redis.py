import json
from typing import Any

from buraq.contrib.cache.backends.base import BaseCacheBackend


class RedisCacheBackend(BaseCacheBackend):
    """
    Redis cache backend using redis.asyncio.
    Shared across all processes/workers — recommended for production.

    Requires: pip install redis[hiredis]
    """

    def __init__(self, url: str | None = None):
        from buraq.conf import settings
        self._url = url or getattr(settings, "CACHE_REDIS_URL", "redis://localhost:6379/0")  # type: ignore[attr-defined]
        self._prefix = getattr(settings, "CACHE_KEY_PREFIX", "")  # type: ignore[attr-defined]
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import redis.asyncio as aioredis
            self._client = aioredis.from_url(self._url, decode_responses=True)
        return self._client

    def _make_key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    async def get(self, key: str) -> Any | None:
        client = await self._get_client()
        raw = await client.get(self._make_key(key))
        if raw is None:
            return None
        return json.loads(raw)

    async def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        client = await self._get_client()
        serialized = json.dumps(value, default=str)
        if timeout:
            await client.setex(self._make_key(key), timeout, serialized)
        else:
            await client.set(self._make_key(key), serialized)

    async def delete(self, key: str) -> None:
        client = await self._get_client()
        await client.delete(self._make_key(key))

    async def exists(self, key: str) -> bool:
        client = await self._get_client()
        return bool(await client.exists(self._make_key(key)))

    async def clear(self) -> None:
        client = await self._get_client()
        keys = await client.keys(f"{self._prefix}*")
        if keys:
            await client.delete(*keys)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
