import pickle
from typing import Any

from buraq.contrib.cache.backends.base import BaseCacheBackend


class MemcachedCacheBackend(BaseCacheBackend):
    """
    Memcached cache backend using aiomcache (pure-async).
    Shared across all processes/workers — recommended for production.

    Requires: pip install aiomcache

    Settings:
        CACHE_MEMCACHED_URL = "memcached://localhost:11211"
        # or multiple servers:
        CACHE_MEMCACHED_SERVERS = [("localhost", 11211), ("cache2", 11211)]
        CACHE_KEY_PREFIX = ""
        CACHE_DEFAULT_TIMEOUT = 300
    """

    def __init__(self):
        from buraq.conf import settings
        self._prefix = getattr(settings, "CACHE_KEY_PREFIX", "").encode()
        self._default_timeout = getattr(settings, "CACHE_DEFAULT_TIMEOUT", 300)
        self._client = None

        url = getattr(settings, "CACHE_MEMCACHED_URL", None)
        servers = getattr(settings, "CACHE_MEMCACHED_SERVERS", None)

        if servers:
            self._servers = servers
        elif url:
            # Parse memcached://host:port
            stripped = url.replace("memcached://", "").replace("memcache://", "")
            host, _, port = stripped.partition(":")
            self._servers = [(host or "localhost", int(port or 11211))]
        else:
            self._servers = [("localhost", 11211)]

    async def _get_client(self):
        if self._client is None:
            import aiomcache
            if len(self._servers) == 1:
                host, port = self._servers[0]
                self._client = aiomcache.Client(host, port)
            else:
                # aiomcache doesn't support pools natively; use first server
                # For multi-server, users should use twemproxy/mcrouter in front
                host, port = self._servers[0]
                self._client = aiomcache.Client(host, port)
        return self._client

    def _make_key(self, key: str) -> bytes:
        # Memcached keys must be bytes, no spaces, max 250 chars
        full = self._prefix + key.encode()
        if len(full) > 250:
            import hashlib
            full = self._prefix + hashlib.md5(key.encode()).hexdigest().encode()
        return full

    async def get(self, key: str) -> Any | None:
        client = await self._get_client()
        raw = await client.get(self._make_key(key))
        if raw is None:
            return None
        return pickle.loads(raw)

    async def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        client = await self._get_client()
        exptime = timeout if timeout is not None else self._default_timeout
        await client.set(self._make_key(key), pickle.dumps(value), exptime=exptime)

    async def delete(self, key: str) -> None:
        client = await self._get_client()
        await client.delete(self._make_key(key))

    async def exists(self, key: str) -> bool:
        client = await self._get_client()
        return await client.get(self._make_key(key)) is not None

    async def clear(self) -> None:
        client = await self._get_client()
        await client.flush_all()

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        client = await self._get_client()
        byte_keys = [self._make_key(k) for k in keys]
        raw_map = await client.multi_get(*byte_keys)
        result = {}
        for k, bkey in zip(keys, byte_keys, strict=False):
            raw = raw_map.get(bkey)
            if raw is not None:
                result[k] = pickle.loads(raw)
        return result

    async def set_many(self, mapping: dict[str, Any], timeout: int | None = None) -> None:
        exptime = timeout if timeout is not None else self._default_timeout
        client = await self._get_client()
        for key, value in mapping.items():
            await client.set(self._make_key(key), pickle.dumps(value), exptime=exptime)

    async def delete_many(self, keys: list[str]) -> None:
        client = await self._get_client()
        for key in keys:
            await client.delete(self._make_key(key))

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
