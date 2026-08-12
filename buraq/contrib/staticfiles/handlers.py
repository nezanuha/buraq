import hashlib
import logging
import shutil
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from buraq.conf import settings

_log = logging.getLogger(__name__)


class StaticFilesHandler:
    """
    Serves static files — development uses FastAPI StaticFiles,
    production uses WhiteNoise for compressed, cached serving.
    """

    def __init__(self, app: FastAPI):
        self.app = app
        static_root = getattr(settings, "STATIC_ROOT", None)
        self._static_root = Path(static_root) if static_root else None
        self._static_dir = Path(settings.STATIC_DIR) if settings.STATIC_DIR else Path("static")

    def mount(self) -> None:
        if settings.DEBUG:
            self._mount_dev()
        else:
            self._mount_production()
        self._mount_media()

    def _mount_dev(self) -> None:
        if self._static_dir.exists():
            self.app.mount(
                settings.STATIC_URL.rstrip("/"),
                StaticFiles(directory=str(self._static_dir)),
                name="static",
            )

    def _mount_production(self) -> None:
        try:
            from whitenoise import WhiteNoise  # type: ignore[import]
            root = self._static_root or self._static_dir
            self.app.mount(
                settings.STATIC_URL.rstrip("/"),
                WhiteNoise(application=None, root=str(root), max_age=31536000),  # type: ignore[arg-type]
                name="static",
            )
        except ImportError:
            _log.warning(
                "whitenoise is not installed — falling back to StaticFiles for production. "
                "Run: uv add whitenoise"
            )
            self._mount_dev()

    def _mount_media(self) -> None:
        media_dir = Path(settings.MEDIA_DIR) if settings.MEDIA_DIR else None
        if media_dir and media_dir.exists():
            self.app.mount(
                settings.MEDIA_URL.rstrip("/"),
                StaticFiles(directory=str(media_dir)),
                name="media",
            )


def collect_static(
    source_dirs: list[str] | None = None,
    dest_dir: str | None = None,
    clear: bool = False,
) -> dict[str, int]:
    """
    Collect static files from all configured sources into STATIC_ROOT.
    Run via: buraq collectstatic

    Uses STATICFILES_FINDERS to discover files and STATICFILES_STORAGE to
    store them (including post-processing such as manifest hashing).

    Returns: {"copied": N, "skipped": N, "post_processed": N}
    """
    from buraq.contrib.staticfiles.storage import get_storage

    storage = get_storage()
    static_root = Path(dest_dir) if dest_dir else Path(storage.location)

    if clear and static_root.exists():
        shutil.rmtree(static_root)

    static_root.mkdir(parents=True, exist_ok=True)

    collected: dict[str, str] = {}
    copied = skipped = 0

    if source_dirs:
        # Legacy / explicit source dirs override finders
        for source in (Path(d) for d in source_dirs):
            if not source.exists():
                continue
            for src_file in source.rglob("*"):
                if not src_file.is_file():
                    continue
                rel = str(src_file.relative_to(source))
                dest_file = static_root / rel
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                if dest_file.exists() and _file_hash(src_file) == _file_hash(dest_file):
                    skipped += 1
                    continue
                shutil.copy2(src_file, dest_file)
                collected[rel] = str(src_file)
                copied += 1
    else:
        from buraq.contrib.staticfiles.finders import get_files
        for rel, full in get_files():
            dest_file = static_root / rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            src_path = Path(full)
            if dest_file.exists() and _file_hash(src_path) == _file_hash(dest_file):
                skipped += 1
                continue
            shutil.copy2(full, dest_file)
            collected[rel] = full
            copied += 1

    post_processed = sum(1 for _ in storage.post_process(collected))

    return {"copied": copied, "skipped": skipped, "post_processed": post_processed}


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()
