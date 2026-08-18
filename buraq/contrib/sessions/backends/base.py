"""
Abstract base class for server-side session backends.

Each backend stores session data keyed by a session_key string and
exposes the same async interface so backends are interchangeable.
"""
from __future__ import annotations

import secrets
import time
from abc import ABC, abstractmethod
from typing import Any


class SessionBase(ABC):
    """
    Common contract for all Buraq server-side session backends.

    Subclasses must implement ``load()``, ``save()``, ``delete()``,
    and ``exists()``.
    """

    SESSION_COOKIE_AGE: int = 1209600  # 2 weeks in seconds
    KEY_SALT = "buraq.contrib.sessions"

    def __init__(self, session_key: str | None = None) -> None:
        self._session_key = session_key
        self._session_cache: dict | None = None
        self.modified = False
        self.accessed = False

    # ── Key generation ────────────────────────────────────────────────────────

    @property
    def session_key(self) -> str | None:
        return self._session_key

    def _get_new_session_key(self) -> str:
        return secrets.token_hex(32)

    async def _get_or_create_session_key(self) -> str:
        if self._session_key is None:
            key = self._get_new_session_key()
            while await self.exists(key):
                key = self._get_new_session_key()
            self._session_key = key
        return self._session_key

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    async def load(self) -> dict:
        """Load and return the session data dict."""

    @abstractmethod
    async def save(self, must_create: bool = False) -> None:
        """Persist the session data.  Raise ValueError if must_create and key exists."""

    @abstractmethod
    async def delete(self, session_key: str | None = None) -> None:
        """Delete the session identified by session_key (or the current key)."""

    @abstractmethod
    async def exists(self, session_key: str) -> bool:
        """Return True if a session with this key exists in the store."""

    # ── Convenience methods ──────────────────────────────────────────────────

    async def _get_session(self, no_load: bool = False) -> dict:
        self.accessed = True
        if self._session_cache is None:
            if self._session_key is None or no_load:
                self._session_cache = {}
            else:
                self._session_cache = await self.load()
        return self._session_cache

    async def get(self, key: str, default: Any = None) -> Any:
        d = await self._get_session()
        return d.get(key, default)

    async def set(self, key: str, value: Any) -> None:
        d = await self._get_session()
        d[key] = value
        self.modified = True

    async def pop(self, key: str, *args) -> Any:
        d = await self._get_session()
        self.modified = key in d
        return d.pop(key, *args)

    async def setdefault(self, key: str, value: Any) -> Any:
        d = await self._get_session()
        if key not in d:
            d[key] = value
            self.modified = True
        return d[key]

    async def keys(self):
        return (await self._get_session()).keys()

    async def values(self):
        return (await self._get_session()).values()

    async def items(self):
        return (await self._get_session()).items()

    async def clear(self) -> None:
        d = await self._get_session()
        d.clear()
        self.modified = True

    def __bool__(self) -> bool:
        """Return True if the session contains any data."""
        if self._session_cache is None:
            return False
        return bool(self._session_cache)

    async def flush(self) -> None:
        """Clear session data and delete the backing store entry."""
        await self.clear()
        if self._session_key:
            await self.delete()
        self._session_key = None

    async def cycle_key(self) -> None:
        """Rotate session key (keeps data, issues a new key)."""
        data = dict(await self._get_session())
        old_key = self._session_key
        self._session_key = None
        self._session_cache = data
        self.modified = True
        await self.save(must_create=True)
        if old_key:
            await self.delete(old_key)

    def set_expiry(self, value: int | None) -> None:
        """Set a custom expiry in seconds. None resets to SESSION_COOKIE_AGE."""
        self._custom_expiry: int | None = value
        self.modified = True

    def get_expiry_age(self) -> int:
        custom = getattr(self, "_custom_expiry", None)
        return custom if custom is not None else self.SESSION_COOKIE_AGE

    def get_expiry_date(self) -> float:
        return time.time() + self.get_expiry_age()

    # ── Encoding helpers ──────────────────────────────────────────────────────

    def _encode(self, data: dict) -> str:
        import json
        return json.dumps(data)

    def _decode(self, raw: str) -> dict:
        import json
        try:
            return json.loads(raw)
        except Exception:
            return {}
