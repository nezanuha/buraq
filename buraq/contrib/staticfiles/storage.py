"""
Static file storage backends.

STATICFILES_STORAGE = "buraq.contrib.staticfiles.storage.StaticFilesStorage"       # default
STATICFILES_STORAGE = "buraq.contrib.staticfiles.storage.ManifestStaticFilesStorage"  # production
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import shutil
from collections.abc import Iterator
from pathlib import Path

from buraq.conf import settings

_log = logging.getLogger(__name__)


class StaticFilesStorage:
    """
    Default storage backend — serves files from the local filesystem as-is.

    URLs are returned as ``STATIC_URL + name`` with no transformation.
    """

    def __init__(self, location: str | None = None, base_url: str | None = None):
        self.location = location or (
            settings.STATIC_ROOT or str(Path.cwd() / "staticfiles")
        )
        self.base_url = (base_url or settings.STATIC_URL).rstrip("/") + "/"

    def path(self, name: str) -> str:
        """Absolute filesystem path for ``name``."""
        return os.path.join(self.location, name.lstrip("/"))

    def url(self, name: str) -> str:
        """Public URL for ``name``."""
        return self.base_url + name.lstrip("/")

    def exists(self, name: str) -> bool:
        return os.path.isfile(self.path(name))

    def save(self, name: str, source_path: str) -> str:
        """Copy ``source_path`` into storage at ``name``. Returns stored name."""
        dest = self.path(name)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(source_path, dest)
        return name

    def post_process(self, collected: dict[str, str]) -> Iterator[tuple[str, str, bool]]:
        """
        Called after collectstatic copies all files.

        Yields ``(original_name, stored_name, processed)`` tuples.
        Override in subclasses to transform files (e.g. hash filenames).
        """
        return iter([])


class ManifestStaticFilesStorage(StaticFilesStorage):
    """
    Storage backend that appends a content hash to each filename after collectstatic.

    ``css/style.css`` becomes ``css/style.abc123de.css``.
    A ``staticfiles.json`` manifest maps original names to hashed names.
    The ``static()`` template function returns the hashed URL automatically —
    zero stale CSS/JS after deploys when combined with long-lived cache headers.

    Usage::

        # config/settings.py
        STATICFILES_STORAGE = "buraq.contrib.staticfiles.storage.ManifestStaticFilesStorage"

    Run ``buraq collectstatic`` after every deploy to regenerate the manifest.
    """

    manifest_name = "staticfiles.json"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._manifest: dict[str, str] = {}
        self._load_manifest()

    # ── Manifest I/O ──────────────────────────────────────────────────────────

    def _manifest_path(self) -> str:
        return os.path.join(self.location, self.manifest_name)

    def _load_manifest(self) -> None:
        path = self._manifest_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._manifest = data.get("paths", {})
            _log.debug("Loaded staticfiles manifest: %d entries", len(self._manifest))
        except Exception:
            _log.exception("Could not load staticfiles manifest at %s", path)
            self._manifest = {}

    def _save_manifest(self) -> None:
        path = self._manifest_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"version": "1.0", "paths": self._manifest}, f, indent=2)
        _log.info("Manifest saved: %d entries → %s", len(self._manifest), path)

    # ── URL lookup ────────────────────────────────────────────────────────────

    def url(self, name: str) -> str:
        """Return the hashed URL from the manifest, falling back to the original name."""
        hashed = self._manifest.get(name.lstrip("/"), name.lstrip("/"))
        return self.base_url + hashed

    # ── Post-processing ───────────────────────────────────────────────────────

    def post_process(self, collected: dict[str, str]) -> Iterator[tuple[str, str, bool]]:
        """
        Hash every collected file, write the hashed copy, update the manifest.

        ``collected`` maps relative name → absolute source path.
        Yields ``(original_name, hashed_name, True)`` for each processed file.
        """
        new_manifest: dict[str, str] = {}

        for name, _source_path in collected.items():
            dest_path = self.path(name)
            if not os.path.isfile(dest_path):
                _log.warning("post_process: %s not found at %s — skipping", name, dest_path)
                continue

            file_hash = self._hash_file(dest_path)
            hashed_name = self._hashed_name(name, file_hash)
            hashed_dest = self.path(hashed_name)

            os.makedirs(os.path.dirname(hashed_dest), exist_ok=True)
            shutil.copy2(dest_path, hashed_dest)
            new_manifest[name] = hashed_name
            yield name, hashed_name, True

        self._manifest = new_manifest
        self._save_manifest()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _hash_file(path: str, length: int = 8) -> str:
        h = hashlib.md5(usedforsecurity=False)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()[:length]

    @staticmethod
    def _hashed_name(name: str, file_hash: str) -> str:
        p = Path(name)
        return str(p.parent / f"{p.stem}.{file_hash}{p.suffix}")


# ── In-memory storage ────────────────────────────────────────────────────────

class InMemoryStorage:
    """
    Volatile in-memory storage backend — no disk I/O, no cleanup needed.

    Designed for tests.  Files are stored as ``bytes`` in a plain dict and
    discarded when the process ends (or when ``clear()`` is called).

    Usage::

        # tests/conftest.py or test setUp
        from buraq.contrib.staticfiles.storage import InMemoryStorage
        storage = InMemoryStorage()
        storage.save("logo.png", b"...")

        # Or globally via settings
        STATICFILES_STORAGE = "buraq.contrib.staticfiles.storage.InMemoryStorage"
    """

    def __init__(self, base_url: str = "/static/"):
        self.base_url = base_url.rstrip("/") + "/"
        self._files: dict[str, bytes] = {}

    def path(self, name: str) -> str:
        raise NotImplementedError("InMemoryStorage has no filesystem path.")

    def url(self, name: str) -> str:
        return self.base_url + name.lstrip("/")

    def exists(self, name: str) -> bool:
        return name.lstrip("/") in self._files

    def save(self, name: str, content: str | bytes | os.PathLike) -> str:
        key = name.lstrip("/")
        if isinstance(content, (str, os.PathLike)):
            with open(content, "rb") as f:
                self._files[key] = f.read()
        else:
            self._files[key] = bytes(content)
        return name

    def open(self, name: str) -> io.BytesIO:
        key = name.lstrip("/")
        if key not in self._files:
            raise FileNotFoundError(name)
        return io.BytesIO(self._files[key])

    def delete(self, name: str) -> None:
        self._files.pop(name.lstrip("/"), None)

    def listdir(self, path: str = "") -> list[str]:
        prefix = path.lstrip("/")
        return [k for k in self._files if k.startswith(prefix)]

    def size(self, name: str) -> int:
        key = name.lstrip("/")
        if key not in self._files:
            raise FileNotFoundError(name)
        return len(self._files[key])

    def clear(self) -> None:
        """Remove all stored files."""
        self._files.clear()

    def post_process(self, collected):
        return iter([])


# ── Singleton accessor ────────────────────────────────────────────────────────

_storage_instance: StaticFilesStorage | None = None


def get_storage() -> StaticFilesStorage:
    """Return the configured storage backend (lazy singleton)."""
    global _storage_instance
    if _storage_instance is None:
        from buraq.utils.module_loading import import_string
        storage_path = getattr(
            settings,
            "STATICFILES_STORAGE",
            "buraq.contrib.staticfiles.storage.StaticFilesStorage",
        )
        storage_cls = import_string(storage_path)
        _storage_instance = storage_cls()
    return _storage_instance


def reset_storage() -> None:
    """Reset the cached storage instance — call after changing STATICFILES_STORAGE in tests."""
    global _storage_instance
    _storage_instance = None
