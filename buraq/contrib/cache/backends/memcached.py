import pickle
from typing import Any

from buraq.contrib.cache.backends.base import BaseCacheBackend


def _as_server(entry) -> tuple[str, int]:
    """Accept ("host", port) as before, and "host:port" as CACHES writes it."""
    if isinstance(entry, (tuple, list)):
        host, port = entry
        return str(host), int(port)
    text = str(entry).replace("memcached://", "").replace("memcache://", "")
    host, _, port = text.partition(":")
    return host or "localhost", int(port or 11211)


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

    def __init__(
        self,
        location: str | list[str] | None = None,
        key_prefix: str | None = None,
        timeout: int | None = None,
        version: int | None = None,
    ):
        """``location`` is the server, or servers, when it comes from a CACHES
        entry -- what it means for Django's memcached backend."""
        from buraq.conf import settings
        self._init_shared(key_prefix, timeout, version)
        self._client = None

        url = getattr(settings, "CACHE_MEMCACHED_URL", None)
        servers = getattr(settings, "CACHE_MEMCACHED_SERVERS", None)

        # A CACHES entry names the server in LOCATION, and saying it there has
        # to beat a project-wide setting -- that is the point of naming it per
        # cache. Django takes a list or a single "host:port".
        if location:
            servers = location if isinstance(location, list) else [location]
        if servers:
            self._servers = [_as_server(s) for s in servers]
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
        # Memcached keys must be bytes, no spaces, max 250 chars. The prefix is
        # a str on the base class, which every other backend uses as one.
        prefix = self._prefix.encode()
        full = prefix + key.encode()
        if len(full) > 250:
            import hashlib
            digest = hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()
            full = prefix + digest.encode()
        return full

    async def get(self, key: str) -> Any | None:
        client = await self._get_client()
        raw = await client.get(self._make_key(key))
        if raw is None:
            return None
        return pickle.loads(raw)

    async def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        client = await self._get_client()
        exptime = self._resolve_timeout(timeout) or 0
        await client.set(self._make_key(key), pickle.dumps(value), exptime=exptime)

    async def add(self, key: str, value: Any, timeout: int | None = None) -> bool:
        """Set the key only if it is not already there.

        ADD is a memcached command, so the server decides and exactly one caller
        wins. The inherited version checks and then sets, and both halves wait on
        the network, so two callers can both find the key missing and both
        believe they set it -- which defeats the point, since `add` is what people
        build locks out of.

        Falls back to the inherited version if the installed client has no
        `add`, rather than failing: a slower correct-enough path beats an
        AttributeError at the first lock.
        """
        client = await self._get_client()
        if not hasattr(client, "add"):  # pragma: no cover - client dependent
            return await super().add(key, value, timeout)
        exptime = self._resolve_timeout(timeout) or 0
        return bool(
            await client.add(self._make_key(key), pickle.dumps(value), exptime=exptime)
        )

    async def incr(self, key: str, delta: int = 1) -> int:
        """Not atomic here, unlike Redis and the database.

        Memcached's own INCR works on values stored as ASCII decimals, and this
        backend stores pickles -- so using it would mean a second storage format
        for integers, and `get` guessing which one it is looking at. That guess
        is wrong for any string that happens to look like a number.

        The inherited read-then-write is used instead, and concurrent callers can
        lose counts. For a counter that has to be right, use Redis or the
        database backend.
        """
        return await super().incr(key, delta)

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
