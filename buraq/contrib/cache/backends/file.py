import asyncio
import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

from buraq.conf import settings
from buraq.contrib.cache.backends.base import BaseCacheBackend


class FileCacheBackend(BaseCacheBackend):
    """
    File-system cache backend.
    Persistent across restarts. Useful for staging/low-traffic apps.
    """

    def __init__(self, cache_dir: str | None = None):
        self._dir = Path(cache_dir or getattr(settings, "CACHE_FILE_PATH", ".cache"))  # type: ignore[attr-defined]
        # Directory creation is deferred to _write_sync (which runs in a thread),
        # avoiding blocking I/O in the constructor which runs on the event loop thread.

    def _key_path(self, key: str) -> Path:
        hashed = hashlib.sha256(key.encode()).hexdigest()
        return self._dir / hashed[:2] / f"{hashed}.json"

    def _read_sync(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["expires_at"] is not None and time.time() > data["expires_at"]:
            path.unlink(missing_ok=True)
            return None
        return data["value"]

    def _write_sync(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, default=str), encoding="utf-8")

    async def get(self, key: str) -> Any | None:
        path = self._key_path(key)
        return await asyncio.to_thread(self._read_sync, path)

    async def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        path = self._key_path(key)
        payload = {
            "key": key,
            "value": value,
            "expires_at": time.time() + timeout if timeout else None,
        }
        await asyncio.to_thread(self._write_sync, path, payload)

    async def delete(self, key: str) -> None:
        path = self._key_path(key)
        await asyncio.to_thread(lambda: path.unlink(missing_ok=True))

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None

    async def clear(self) -> None:
        cache_dir = self._dir

        def _clear_sync():
            shutil.rmtree(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)

        await asyncio.to_thread(_clear_sync)
