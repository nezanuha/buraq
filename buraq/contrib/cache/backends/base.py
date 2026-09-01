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
        self, key_prefix: str | None = None, timeout: int | None = None
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

    def _make_key(self, key: str) -> str:
        """The key as it is stored, with whatever prefix applies."""
        return f"{getattr(self, '_prefix', '')}{key}"

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
