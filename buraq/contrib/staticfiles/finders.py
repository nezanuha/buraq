"""
Static file finders — locate static files across multiple source directories.

Configured via STATICFILES_FINDERS in settings.
"""
from __future__ import annotations

import importlib
import logging
from pathlib import Path

from buraq.conf import settings

_log = logging.getLogger(__name__)


class FileSystemFinder:
    """
    Finds static files in STATICFILES_DIRS (and the legacy STATIC_DIR).

    Listed directories are searched in order; the first match wins.
    """

    def __init__(self):
        dirs: list[str] = list(getattr(settings, "STATICFILES_DIRS", []))
        # Backward-compat: STATIC_DIR is treated as an extra entry
        static_dir = getattr(settings, "STATIC_DIR", None)
        if static_dir and static_dir not in dirs:
            dirs.append(static_dir)
        self.dirs = dirs

    def find(self, path: str) -> str | None:
        """Return the absolute path of ``path`` if it exists in any configured dir."""
        for root in self.dirs:
            full = Path(root) / path
            if full.is_file():
                return str(full)
        return None

    def list(self):
        """Yield ``(relative_path, absolute_path)`` for every file in every dir."""
        seen: set[str] = set()
        for root in self.dirs:
            root_path = Path(root)
            if not root_path.is_dir():
                _log.debug("FileSystemFinder: %s does not exist, skipping", root)
                continue
            for file_path in root_path.rglob("*"):
                if not file_path.is_file():
                    continue
                rel = file_path.relative_to(root_path).as_posix()
                if rel not in seen:
                    seen.add(rel)
                    yield rel, str(file_path)


class AppDirectoriesFinder:
    """
    Finds static files inside each installed app's ``static/`` subdirectory.

    Finds static files inside each installed app's ``static/`` directory.
    """

    def find(self, path: str) -> str | None:
        for app_name in settings.INSTALLED_APPS:
            app_static = self._app_static_dir(app_name)
            if app_static:
                full = Path(app_static) / path
                if full.is_file():
                    return str(full)
        return None

    def list(self):
        seen: set[str] = set()
        for app_name in settings.INSTALLED_APPS:
            app_static = self._app_static_dir(app_name)
            if not app_static:
                continue
            static_path = Path(app_static)
            for file_path in static_path.rglob("*"):
                if not file_path.is_file():
                    continue
                rel = file_path.relative_to(static_path).as_posix()
                if rel not in seen:
                    seen.add(rel)
                    yield rel, str(file_path)

    @staticmethod
    def _app_static_dir(app_name: str) -> str | None:
        try:
            mod = importlib.import_module(app_name)
            if mod.__file__:
                static_dir = Path(mod.__file__).parent / "static"
                if static_dir.is_dir():
                    return str(static_dir)
        except (ImportError, AttributeError):
            pass
        return None


# ── Module-level helpers ──────────────────────────────────────────────────────

def get_finders() -> list:
    """Return instantiated finder objects from STATICFILES_FINDERS."""
    from buraq.utils.module_loading import import_string
    finders = []
    for finder_path in getattr(settings, "STATICFILES_FINDERS", []):
        try:
            finder_cls = import_string(finder_path)
            finders.append(finder_cls())
        except Exception:
            _log.exception("Could not load static files finder: %s", finder_path)
    return finders


def find(path: str) -> str | None:
    """Find a static file by relative path. Returns absolute path or None."""
    for finder in get_finders():
        result = finder.find(path)
        if result:
            return result
    return None


def get_files():
    """
    Yield ``(relative_path, absolute_path)`` for every static file across all finders.

    Deduplicates by relative path — first finder to provide a file wins.
    """
    seen: set[str] = set()
    for finder in get_finders():
        for rel, full in finder.list():
            if rel not in seen:
                seen.add(rel)
                yield rel, full
