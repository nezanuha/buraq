"""
Cache-backed session backend.

Uses the configured Buraq cache (see CACHES / CACHE_BACKEND) to store sessions.
No database table required; sessions expire automatically when the cache entry expires.

Settings::

    SESSION_ENGINE = "buraq.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"   # optional — which CACHES entry to use
"""
from __future__ import annotations

from buraq.contrib.sessions.backends.base import SessionBase

_KEY_PREFIX = "buraq_session:"


def _get_cache():
    try:
        from buraq.conf import settings
        alias = getattr(settings, "SESSION_CACHE_ALIAS", "default")
    except Exception:
        alias = "default"
    from buraq.contrib.cache.core import caches
    return caches[alias]


class CachedSessionBackend(SessionBase):
    """Stores session data in the configured cache backend."""

    def _cache_key(self, key: str) -> str:
        return f"{_KEY_PREFIX}{key}"

    async def exists(self, session_key: str) -> bool:
        cache = _get_cache()
        return await cache.exists(self._cache_key(session_key))

    async def load(self) -> dict:
        cache = _get_cache()
        data = await cache.get(self._cache_key(self._session_key))
        if data is None:
            self._session_key = None
            return {}
        return self._decode(data) if isinstance(data, str) else data

    async def save(self, must_create: bool = False) -> None:
        key = await self._get_or_create_session_key()
        cache = _get_cache()
        cache_key = self._cache_key(key)
        if must_create and await cache.exists(cache_key):
            raise ValueError(f"Session key {key!r} already exists.")
        await cache.set(
            cache_key,
            self._session_cache or {},
            timeout=self.get_expiry_age(),
        )

    async def delete(self, session_key: str | None = None) -> None:
        key = session_key or self._session_key
        if key:
            cache = _get_cache()
            await cache.delete(self._cache_key(key))
