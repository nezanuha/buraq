import asyncio
import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

from buraq.conf import settings
from buraq.contrib.cache.backends.base import BaseCacheBackend


def _to_json(document, key: str, backend: str, subject=None) -> str:
    """
    Serialize a cache value, refusing what JSON cannot represent.

    ``default=str`` used to stand in for this, which turned an unserializable
    value into its repr: a datetime went in and a string came back, and the
    mismatch surfaced wherever the value was next used rather than at the call
    that cached it.
    """
    try:
        return json.dumps(document)
    except TypeError as err:
        # `document` may be an envelope around the cached value; name the value's
        # type, which is the part the caller chose.
        offending = document if subject is None else subject
        raise TypeError(
            f"{backend} stores values as JSON and cannot serialize "
            f"{type(offending).__name__} (key {key!r}). Cache a JSON-friendly "
            f"value, or use a backend that pickles -- see the cache documentation."
        ) from err


class FileCacheBackend(BaseCacheBackend):
    """
    File-system cache backend.
    Persistent across restarts. Useful for staging/low-traffic apps.
    """

    def __init__(
        self,
        cache_dir: str | None = None,
        location: str | None = None,
        key_prefix: str | None = None,
        timeout: int | None = None,
        version: int | None = None,
    ):
        """``location`` is the directory when it comes from a CACHES entry, which
        is what it means for Django's file-based cache."""
        self._dir = Path(cache_dir or location or getattr(settings, "CACHE_FILE_PATH", ".cache"))  # type: ignore[attr-defined]
        self._init_shared(key_prefix, timeout, version)
        self._lock: asyncio.Lock | None = None  # made lazily, inside the loop
        # Directory creation is deferred to _write_sync (which runs in a thread),
        # avoiding blocking I/O in the constructor which runs on the event loop thread.

    def _key_path(self, key: str) -> Path:
        hashed = hashlib.sha256(self._make_key(key).encode()).hexdigest()
        return self._dir / hashed[:2] / f"{hashed}.json"

    def _read_sync(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["expires_at"] is not None and time.time() > data["expires_at"]:
            path.unlink(missing_ok=True)
            return None
        return data["value"]

    def _write_sync(self, path: Path, document: str) -> None:
        """Write the entry so a reader never sees half of it.

        Writing in place leaves the file short and unparseable for as long as it
        takes, and a crash partway leaves it that way for good. Writing beside it
        and renaming is atomic on both POSIX and Windows, so a reader sees either
        the old entry or the new one.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f".{os.getpid()}.tmp")
        try:
            temporary.write_text(document, encoding="utf-8")
            os.replace(temporary, path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    def _add_sync(self, path: Path, document: str) -> bool:
        """Create the entry only if it is not already there.

        O_CREAT|O_EXCL is one operation the operating system decides, so exactly
        one caller wins even across processes -- which matters here, since a file
        cache is usually shared by several.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        # An expired entry still occupies the name; clear it, or a lock could
        # never be taken again once it had expired.
        if self._read_sync(path) is None:
            path.unlink(missing_ok=True)
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            fh.write(document)
        return True

    async def add(self, key: str, value: Any, timeout: int | None = None) -> bool:
        timeout = self._resolve_timeout(timeout)
        document = _to_json(
            {
                "key": key,
                "value": value,
                "expires_at": time.time() + timeout if timeout and timeout > 0 else None,
            },
            key,
            "FileCacheBackend",
            subject=value,
        )
        return await asyncio.to_thread(self._add_sync, self._key_path(key), document)

    async def incr(self, key: str, delta: int = 1) -> int:
        """Add to the integer at the key.

        Held under this process's lock, which is all that can be promised: making
        a read-modify-write safe between processes needs an OS file lock, and the
        portable ones behave differently enough on Windows that a wrong one is
        worse than an honest limit. For a counter several processes share, use
        Redis or the database backend.
        """
        async with self._get_lock():
            current = await self.get(key)
            if current is None:
                raise ValueError(f"Cache key {key!r} not found.")
            new_value = int(current) + delta
            await self.set(key, new_value)
            return new_value

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def get(self, key: str) -> Any | None:
        path = self._key_path(key)
        return await asyncio.to_thread(self._read_sync, path)

    async def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        timeout = self._resolve_timeout(timeout)
        path = self._key_path(key)
        payload = {
            "key": key,
            "value": value,
            "expires_at": time.time() + timeout if timeout and timeout > 0 else None,
        }
        # Serialized here rather than in the thread, so an unserializable value
        # raises from the call that cached it.
        document = _to_json(payload, key, "FileCacheBackend", subject=value)
        await asyncio.to_thread(self._write_sync, path, document)

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
