"""
File storage backends.

``Storage``           — abstract base
``FileSystemStorage`` — stores files on the local filesystem
``default_storage``   — lazy proxy to the configured storage backend

Usage::

    from buraq.core.files.storage import default_storage, FileSystemStorage

    # Save
    name = await default_storage.save("uploads/photo.jpg", content_file)

    # Check existence
    exists = await default_storage.exists("uploads/photo.jpg")

    # Public URL
    url = default_storage.url("uploads/photo.jpg")

    # Delete
    await default_storage.delete("uploads/photo.jpg")
"""
from __future__ import annotations

import os
import pathlib


class Storage:
    """Abstract base class for file storage backends."""

    async def save(self, name: str, content) -> str:
        raise NotImplementedError

    async def open(self, name: str, mode: str = "rb"):
        raise NotImplementedError

    async def delete(self, name: str) -> None:
        raise NotImplementedError

    async def exists(self, name: str) -> bool:
        raise NotImplementedError

    def url(self, name: str) -> str:
        raise NotImplementedError

    async def size(self, name: str) -> int:
        raise NotImplementedError

    async def listdir(self, path: str) -> tuple[list, list]:
        """Return (directories, files) under ``path``."""
        raise NotImplementedError

    def get_available_name(self, name: str) -> str:
        """Return ``name`` unchanged; subclasses may append a suffix."""
        return name


class FileSystemStorage(Storage):
    """
    Store files on the local filesystem.

    Args:
        location: Absolute path to the directory where files are stored.
                  Defaults to ``settings.MEDIA_DIR``.
        base_url: URL prefix for serving the stored files.
                  Defaults to ``settings.MEDIA_URL``.

    Usage::

        storage = FileSystemStorage(location="/var/media", base_url="/media/")
        name = await storage.save("avatar.jpg", content_file)
        print(storage.url(name))   # → "/media/avatar.jpg"
    """

    def __init__(self, location: str | None = None, base_url: str | None = None):
        if location is None:
            from buraq.conf import settings
            location = settings.MEDIA_DIR or "./media"
        if base_url is None:
            from buraq.conf import settings
            base_url = settings.MEDIA_URL
        self.location = os.path.abspath(location)
        self.base_url = base_url.rstrip("/") + "/"

    def _full_path(self, name: str) -> str:
        safe = os.path.normpath(name).lstrip(os.sep)
        return os.path.join(self.location, safe)

    def get_available_name(self, name: str) -> str:
        path = self._full_path(name)
        if not os.path.exists(path):
            return name
        stem, ext = os.path.splitext(name)
        counter = 1
        while os.path.exists(self._full_path(f"{stem}_{counter}{ext}")):
            counter += 1
        return f"{stem}_{counter}{ext}"

    async def save(self, name: str, content) -> str:
        import asyncio

        name = self.get_available_name(name)
        full_path = self._full_path(name)
        pathlib.Path(full_path).parent.mkdir(parents=True, exist_ok=True)

        def _write():
            with open(full_path, "wb") as fh:
                for chunk in content.chunks():
                    fh.write(chunk)

        await asyncio.get_event_loop().run_in_executor(None, _write)
        return name

    async def open(self, name: str, mode: str = "rb"):
        import asyncio

        full_path = self._full_path(name)

        def _open():
            return open(full_path, mode)

        return await asyncio.get_event_loop().run_in_executor(None, _open)

    async def delete(self, name: str) -> None:
        import asyncio

        full_path = self._full_path(name)

        def _delete():
            if os.path.exists(full_path):
                os.remove(full_path)

        await asyncio.get_event_loop().run_in_executor(None, _delete)

    async def exists(self, name: str) -> bool:
        import asyncio

        full_path = self._full_path(name)
        return await asyncio.get_event_loop().run_in_executor(None, os.path.exists, full_path)

    def url(self, name: str) -> str:
        safe = name.replace(os.sep, "/").lstrip("/")
        return self.base_url + safe

    async def size(self, name: str) -> int:
        import asyncio

        full_path = self._full_path(name)
        return await asyncio.get_event_loop().run_in_executor(None, os.path.getsize, full_path)

    async def listdir(self, path: str) -> tuple[list, list]:
        import asyncio

        full_path = self._full_path(path)

        def _list():
            dirs, files = [], []
            for entry in os.scandir(full_path):
                (dirs if entry.is_dir() else files).append(entry.name)
            return dirs, files

        return await asyncio.get_event_loop().run_in_executor(None, _list)


class _DefaultStorage:
    """Lazy proxy — instantiated on first access from settings."""

    _instance: Storage | None = None

    def _get(self) -> Storage:
        if self._instance is None:
            import importlib

            from buraq.conf import settings

            backend_path = getattr(settings, "DEFAULT_FILE_STORAGE", None)
            if backend_path:
                module_path, class_name = backend_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                self._instance = getattr(module, class_name)()
            else:
                self._instance = FileSystemStorage()
        return self._instance

    def __getattr__(self, name):
        return getattr(self._get(), name)

    async def save(self, name: str, content) -> str:
        return await self._get().save(name, content)

    async def open(self, name: str, mode: str = "rb"):
        return await self._get().open(name, mode)

    async def delete(self, name: str) -> None:
        return await self._get().delete(name)

    async def exists(self, name: str) -> bool:
        return await self._get().exists(name)

    def url(self, name: str) -> str:
        return self._get().url(name)

    async def size(self, name: str) -> int:
        return await self._get().size(name)

    async def listdir(self, path: str) -> tuple[list, list]:
        return await self._get().listdir(path)


default_storage = _DefaultStorage()
