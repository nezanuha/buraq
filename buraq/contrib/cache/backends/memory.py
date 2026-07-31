import asyncio
import time
from typing import Any

from buraq.contrib.cache.backends.base import BaseCacheBackend


class MemoryCacheBackend(BaseCacheBackend):
    """
    In-process memory cache with TTL support.
    Fast — zero network overhead. Not shared across processes.
    """

    def __init__(self, max_size: int = 1000):
        self._store: dict[str, tuple[Any, float | None]] = {}
        self._max_size = max_size
        self._lock = asyncio.Lock()

    def _is_expired(self, expires_at: float | None) -> bool:
        return expires_at is not None and time.monotonic() > expires_at

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if self._is_expired(expires_at):
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        async with self._lock:
            if len(self._store) >= self._max_size and key not in self._store:
                # Evict the oldest key (simple LRU approximation)
                oldest = next(iter(self._store))
                del self._store[oldest]
            expires_at = time.monotonic() + timeout if timeout is not None else None
            self._store[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()
