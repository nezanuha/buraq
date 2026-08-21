import json
from typing import Any

from buraq.contrib.cache.backends.base import BaseCacheBackend


def _to_json(document, key: str, backend: str, subject=None) -> str:
    """
    Serialize a cache value, refusing what JSON cannot represent.

    ``default=str`` used to stand in for this, which turned an unserializable
    value into its repr: a datetime went in and a string came back, and the
    mismatch surfaced wherever the value was next used rather than at the call
    that cached it.
    """
    try:
        return json.dumps(document)
    except TypeError as err:
        # `document` may be an envelope around the cached value; name the value's
        # type, which is the part the caller chose.
        offending = document if subject is None else subject
        raise TypeError(
            f"{backend} stores values as JSON and cannot serialize "
            f"{type(offending).__name__} (key {key!r}). Cache a JSON-friendly "
            f"value, or use a backend that pickles -- see the cache documentation."
        ) from err


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
        serialized = _to_json(value, key, "RedisCacheBackend")
        if timeout is not None and timeout > 0:
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

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        if not keys:
            return {}
        client = await self._get_client()
        prefixed = [self._make_key(k) for k in keys]
        values = await client.mget(*prefixed)
        result = {}
        for k, raw in zip(keys, values, strict=False):
            result[k] = json.loads(raw) if raw is not None else None
        return result

    async def set_many(self, mapping: dict[str, Any], timeout: int | None = None) -> None:
        if not mapping:
            return
        client = await self._get_client()
        async with client.pipeline(transaction=False) as pipe:
            for key, value in mapping.items():
                serialized = _to_json(value, key, "RedisCacheBackend")
                if timeout is not None and timeout > 0:
                    pipe.setex(self._make_key(key), timeout, serialized)
                else:
                    pipe.set(self._make_key(key), serialized)
            await pipe.execute()

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
