"""
File-based session backend.

Stores each session as a JSON file under SESSION_FILE_PATH (default: /tmp/buraq_sessions).
Sessions are automatically expired on access.

Settings::

    SESSION_ENGINE = "buraq.contrib.sessions.backends.file"
    SESSION_FILE_PATH = "/tmp/buraq_sessions"   # optional
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

from buraq.contrib.sessions.backends.base import SessionBase


def _get_storage_path() -> Path:
    try:
        from buraq.conf import settings
        p = getattr(settings, "SESSION_FILE_PATH", None)
        if p:
            return Path(p)
    except Exception:
        pass
    return Path(os.environ.get("BURAQ_SESSION_PATH", "/tmp/buraq_sessions"))


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


class FileSessionBackend(SessionBase):
    """
    Stores session data in one file per session under SESSION_FILE_PATH.

    File format::

        {"data": {...}, "expires": <unix timestamp>}
    """

    def _session_file(self, key: str) -> Path:
        return _get_storage_path() / f"session_{key}"

    async def exists(self, session_key: str) -> bool:
        path = self._session_file(session_key)
        return await asyncio.to_thread(path.exists)

    async def load(self) -> dict:
        path = self._session_file(self._session_key)

        def _read() -> tuple[dict, bool]:
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if raw.get("expires", 0) < time.time():
                    path.unlink(missing_ok=True)
                    return {}, True  # expired
                return raw.get("data", {}), False
            except Exception:
                return {}, True

        data, expired = await asyncio.to_thread(_read)
        if expired:
            self._session_key = None
        return data

    async def save(self, must_create: bool = False) -> None:
        key = await self._get_or_create_session_key()

        def _write() -> None:
            storage = _ensure_dir(_get_storage_path())
            path = storage / f"session_{key}"
            if must_create and path.exists():
                raise ValueError(f"Session key {key!r} already exists.")
            payload = {
                "data": self._session_cache or {},
                "expires": self.get_expiry_date(),
            }
            path.write_text(json.dumps(payload), encoding="utf-8")

        await asyncio.to_thread(_write)

    async def delete(self, session_key: str | None = None) -> None:
        key = session_key or self._session_key
        if key:
            path = self._session_file(key)
            await asyncio.to_thread(path.unlink, True)

    async def clear_expired(self) -> int:
        """Remove all expired session files. Returns count deleted."""
        def _cull() -> int:
            storage = _get_storage_path()
            if not storage.exists():
                return 0
            now = time.time()
            removed = 0
            for f in storage.glob("session_*"):
                try:
                    raw = json.loads(f.read_text(encoding="utf-8"))
                    if raw.get("expires", 0) < now:
                        f.unlink()
                        removed += 1
                except Exception:
                    pass
            return removed

        return await asyncio.to_thread(_cull)
