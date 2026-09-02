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

    def __init__(
        self,
        url: str | None = None,
        location: str | None = None,
        key_prefix: str | None = None,
        timeout: int | None = None,
        version: int | None = None,
    ):
        """``location`` is what a CACHES entry calls the server, as in Django."""
        from buraq.conf import settings
        self._url = url or location or getattr(settings, "CACHE_REDIS_URL", "redis://localhost:6379/0")  # type: ignore[attr-defined]
        self._init_shared(key_prefix, timeout, version)
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import redis.asyncio as aioredis
            self._client = aioredis.from_url(self._url, decode_responses=True)
        return self._client

    async def get(self, key: str) -> Any | None:
        client = await self._get_client()
        raw = await client.get(self._make_key(key))
        if raw is None:
            return None
        return json.loads(raw)

    async def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        client = await self._get_client()
        serialized = _to_json(value, key, "RedisCacheBackend")
        timeout = self._resolve_timeout(timeout)
        if timeout is not None and timeout > 0:
            await client.setex(self._make_key(key), timeout, serialized)
        else:
            await client.set(self._make_key(key), serialized)

    async def add(self, key: str, value: Any, timeout: int | None = None) -> bool:
        """Set the key only if it is not already there.

        Redis does this in one command. The inherited version checks and then
        sets, so two callers could both find the key missing and both believe
        they set it -- which defeats the point, since `add` is the primitive
        people build locks out of.
        """
        client = await self._get_client()
        serialized = _to_json(value, key, "RedisCacheBackend")
        timeout = self._resolve_timeout(timeout)
        ttl = timeout if timeout is not None and timeout > 0 else None
        return bool(await client.set(self._make_key(key), serialized, nx=True, ex=ttl))

    async def incr(self, key: str, delta: int = 1) -> int:
        """Add to the integer at the key, in one command.

        The inherited version reads, adds, and writes back, so two workers
        incrementing at once both read 5, both write 6, and one increment is
        lost. That is the case a counter exists for.

        Integers are stored as their JSON, which for an integer is just its
        digits, so INCRBY reads and leaves exactly what get() expects.

        The increment is atomic; the missing-key check is a separate command, so
        a key that expires between the two is recreated at `delta` rather than
        raising. That is a far smaller problem than losing counts, and avoiding
        it entirely needs a Lua script this cannot test without a live server.
        """
        client = await self._get_client()
        full = self._make_key(key)
        if not await client.exists(full):
            raise ValueError(f"Cache key {key!r} not found.")
        return await client.incrby(full, delta)

    async def delete(self, key: str) -> None:
        client = await self._get_client()
        await client.delete(self._make_key(key))

    async def exists(self, key: str) -> bool:
        client = await self._get_client()
        return bool(await client.exists(self._make_key(key)))

    async def clear(self) -> None:
        """Delete this cache's keys.

        Over SCAN rather than KEYS: KEYS walks the whole keyspace in one blocking
        call, and Redis serves nothing else while it does -- on a large database
        that is a stall measured in seconds, which is why Redis documents it as
        unsuitable for production.

        With no CACHE_KEY_PREFIX set this still matches every key in the
        database, including anything else sharing it -- sessions, and the rate
        limiter when it follows CACHE_REDIS_URL. Set a prefix to scope it.
        """
        client = await self._get_client()
        pattern = f"{self._prefix}*"
        batch: list[str] = []
        async for key in client.scan_iter(match=pattern, count=500):
            batch.append(key)
            if len(batch) >= 500:
                await client.delete(*batch)
                batch.clear()
        if batch:
            await client.delete(*batch)

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
        # set() applies the default; set_many() writing entries that never
        # expire would be the same leak by a different door.
        timeout = self._resolve_timeout(timeout)
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
