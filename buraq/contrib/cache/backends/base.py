import asyncio
from abc import ABC, abstractmethod
from typing import Any


class BaseCacheBackend(ABC):
    """A cache backend.

    Two things every backend has to agree on live here, because leaving them to
    each backend meant they disagreed. `cache.set(key, value)` with no timeout
    did four different things -- never expired on Redis, on memory and in files,
    expired after a hardcoded 300s in the database -- and only memcached read
    CACHE_DEFAULT_TIMEOUT at all. A cache whose entries never expire is not a
    cache; it is a memory leak with a lookup method.

    CACHE_KEY_PREFIX had the same problem from the other end: honoured by Redis
    and memcached, ignored by the rest, so a prefix separating two environments
    in one store silently stopped separating them if the backend changed.

    Subclasses take `key_prefix` and `timeout` so a CACHES entry can set them per
    cache, and fall back to the settings when it does not.
    """

    #: Set by a subclass that applies expiry itself and wants no default filled
    #: in -- nothing does today, but a backend with no notion of TTL would.
    supports_timeout = True

    def _init_shared(
        self,
        key_prefix: str | None = None,
        timeout: int | None = None,
        version: int | None = None,
    ) -> None:
        """Call from a subclass __init__ to pick up the shared settings."""
        from buraq.conf import settings

        self._prefix = (
            key_prefix
            if key_prefix is not None
            else getattr(settings, "CACHE_KEY_PREFIX", "")
        ) or ""
        self._default_timeout = (
            timeout
            if timeout is not None
            else getattr(settings, "CACHE_DEFAULT_TIMEOUT", 300)
        )
        self._version = (
            version if version is not None else getattr(settings, "CACHE_VERSION", 1)
        )

    def _make_key(self, key: str, version: int | None = None) -> str:
        """The key as it is stored: prefix, version, then the key itself.

        The version is what lets a deploy invalidate everything at once without
        emptying the cache: raise ``CACHE_VERSION`` and yesterday's entries stop
        being found, then age out on their own. Changing the prefix does that
        too, but leaves no way to read the old value -- so every miss goes to the
        database at once, which on a busy site is the stampede the cache existed
        to prevent. With a version you can still ask for the old one while you
        roll over.
        """
        if version is None:
            version = getattr(self, "_version", 1)
        return f"{getattr(self, '_prefix', '')}{version}:{key}"

    def with_version(self, version: int):
        """This cache, reading and writing at another version.

        The point of versioning is a rollover you can survive: raise
        CACHE_VERSION so new writes land under the new number, and read the old
        one while the new entries fill in, rather than taking every miss at once
        the moment the cache goes cold.

            previous = cache.with_version(cache.version - 1)
            value = await previous.get("key")

        Shallow, so the connection is shared rather than opened again.
        """
        import copy

        other = copy.copy(self)
        other._version = version
        return other

    @property
    def version(self) -> int:
        return getattr(self, "_version", 1)

    def _resolve_timeout(self, timeout: int | None) -> int | None:
        """The timeout to use when the caller did not give one.

        ``0`` and negative values mean "do not expire", which is how a caller
        asks for that deliberately -- distinct from not passing one at all.
        """
        if timeout is not None:
            return timeout
        return getattr(self, "_default_timeout", None)

    @abstractmethod
    async def get(self, key: str) -> Any | None: ...

    @abstractmethod
    async def set(self, key: str, value: Any, timeout: int | None = None) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def clear(self) -> None: ...

    async def get_or_set(self, key: str, default: Any, timeout: int | None = None) -> Any:
        value = await self.get(key)
        if value is None:
            value = default() if callable(default) else default
            await self.set(key, value, timeout)
        return value

    async def add(self, key: str, value: Any, timeout: int | None = None) -> bool:
        """Set key only if not already present. Returns True if the key was set."""
        if await self.exists(key):
            return False
        await self.set(key, value, timeout)
        return True

    async def incr(self, key: str, delta: int = 1) -> int:
        """Increment the integer value stored at key. Raises ValueError if key missing."""
        current = await self.get(key)
        if current is None:
            raise ValueError(f"Cache key {key!r} not found.")
        new_value = int(current) + delta
        await self.set(key, new_value)
        return new_value

    async def decr(self, key: str, delta: int = 1) -> int:
        """Decrement the integer value stored at key."""
        return await self.incr(key, -delta)

    async def touch(self, key: str, timeout: int | None = None) -> bool:
        """Give the entry a new lifetime without rewriting its value.

        For something expensive to build that is still current -- a session, a
        rendered page -- where set() would mean fetching and re-serialising a
        value that has not changed.

        Returns False when the key is not there, so a caller can tell "kept
        alive" from "already gone" and rebuild.
        """
        value = await self.get(key)
        if value is None:
            return False
        await self.set(key, value, timeout)
        return True

    async def incr_version(self, key: str, delta: int = 1) -> int:
        """Move a value to a later version, leaving nothing behind at the old one.

        The per-key counterpart to raising CACHE_VERSION: it invalidates one
        entry for readers on the current version while keeping the value
        reachable to anything that has already moved on.
        """
        value = await self.get(key)
        if value is None:
            raise ValueError(f"Cache key {key!r} not found.")
        new_version = self.version + delta
        await self.with_version(new_version).set(key, value)
        await self.delete(key)
        return new_version

    async def decr_version(self, key: str, delta: int = 1) -> int:
        """Move a value to an earlier version."""
        return await self.incr_version(key, -delta)

    async def close(self) -> None:
        """Release whatever the backend holds open.

        Nothing to do for a backend that keeps no connection, which is why this
        is not abstract -- every backend can be closed, and most need not do
        anything about it.
        """
        return None

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        values = await asyncio.gather(*(self.get(k) for k in keys))
        return dict(zip(keys, values, strict=True))

    async def set_many(self, mapping: dict[str, Any], timeout: int | None = None) -> None:
        await asyncio.gather(*(self.set(k, v, timeout) for k, v in mapping.items()))

    async def delete_many(self, keys: list[str]) -> None:
        await asyncio.gather(*(self.delete(k) for k in keys))

    # ── Sync wrappers ──────────────────────────────────────────────────────────
    # These run the coroutine in a dedicated background thread with its own
    # event loop so they work correctly regardless of whether the caller is
    # already inside a running loop (e.g. in an async request handler).

    def _run_async(self, coro):
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()

    def get_sync(self, key: str) -> Any | None:
        return self._run_async(self.get(key))

    def set_sync(self, key: str, value: Any, timeout: int | None = None) -> None:
        self._run_async(self.set(key, value, timeout))

    def delete_sync(self, key: str) -> None:
        self._run_async(self.delete(key))

    def delete_many_sync(self, keys: list[str]) -> None:
        self._run_async(self.delete_many(keys))

    def clear_sync(self) -> None:
        self._run_async(self.clear())
