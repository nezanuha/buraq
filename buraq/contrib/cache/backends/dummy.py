"""
A cache that stores nothing.

Every write succeeds and every read misses, so the code around it runs exactly
as it will in production while nothing is remembered between requests.

Two things it is for. In development, it keeps a stale entry from hiding a
change you just made, without having to remember which pages are cached. In
tests, it makes a cache-dependent path deterministic: a test that passes only
because an earlier test warmed the cache is a test that will fail alone, and in
whatever order the suite happens to run next.

    CACHE_URL = "dummy://"
"""
from __future__ import annotations

from typing import Any

from buraq.contrib.cache.backends.base import BaseCacheBackend


class DummyCacheBackend(BaseCacheBackend):
    """Accepts everything, keeps nothing."""

    def __init__(
        self,
        location: str | None = None,
        key_prefix: str | None = None,
        timeout: int | None = None,
        version: int | None = None,
    ):
        self._init_shared(key_prefix, timeout, version)

    async def get(self, key: str) -> Any | None:
        return None

    async def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        return None

    async def delete(self, key: str) -> None:
        return None

    async def exists(self, key: str) -> bool:
        return False

    async def clear(self) -> None:
        return None

    async def add(self, key: str, value: Any, timeout: int | None = None) -> bool:
        """Always True: nothing is stored, so the key is never already taken.

        Which means this backend cannot hold a lock. Code that uses `add` that
        way runs its guarded section every time -- correct for a cache that
        remembers nothing, and worth knowing before pointing a lock at it.
        """
        return True

    async def incr(self, key: str, delta: int = 1) -> int:
        """Raises, as it would on any backend where the key is absent."""
        raise ValueError(f"Cache key {key!r} not found.")

    async def touch(self, key: str, timeout: int | None = None) -> bool:
        return False

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        return {}

    async def set_many(self, mapping: dict[str, Any], timeout: int | None = None) -> None:
        return None

    async def delete_many(self, keys: list[str]) -> None:
        return None
